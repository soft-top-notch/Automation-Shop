from tracing.rl.rewards import PopupRewardsCalculator
from tracing.rl.environment import Environment
import tracing.selenium_utils.common as common

import threading
import csv, re
import random
import traceback
import time
import os, os.path
import json
import uuid
from queue import Queue

import scipy.misc as misc

num_threads = 8
resources = '../../../resources/'
queue = Queue()
dataset_file = resources + 'popups_dataset.csv'
img_folder = 'popups_dataset_imgs/'


def dataset_item_to_str(item):
    return '{}\t{}\t{}\t{}\t{}'.format(
        item['url'], 
        item['has_popup'], 
        item['img_file'], 
        item['author'],
        item['to_classify']
    )


def str_to_dataset_item(line):
    parts = line.split('\t')
    return {
       'url': parts[0],
       'has_popup': parts[1] == 'True',
       'img_file': parts[2],
       'author': parts[3],
       'to_classify': len(parts) == 4 or parts[4] == 'True'
    }


def load_dataset(dataset_file):
    result = []
    with open(dataset_file, 'r') as f:
        for row in f:
            item = str_to_dataset_item(row.strip())
            result.append(item)
    
    return result


def create_driver():
    for i in range(10):
        try:
            driver = common.create_chrome_driver(headless = True, size=(1280, 1024))
            driver.set_page_load_timeout(120)
            return driver
        except:
            time.sleep(2)
        
    raise Exception("can't create driver")


def read_small_image(url):
    file = url['img_file']
    assert os.path.isfile(file)
    create_small_picture(url)
    return misc.imread(get_small_picture(file))
    

def get_small_picture(file):
    assert file[-4:] == '.png', 'file format {} is not supported only png'.format(file)
    first_part = file[:-4]
    
    return first_part + '_small.png'


def create_small_picture(url, width=300):
    file = url['img_file']
    
    small_file = get_small_picture(file)
    if not os.path.isfile(small_file):
        # Resize image
        img = PIL.Image.open(file)
        scale = width / float(img.size[0])

        height = int((img.size[1] * scale))
        img = img.resize((width, height), PIL.Image.ANTIALIAS)
        img.save(small_file)


def create_small_pictures(urls, width=300):
    for i, url in enumerate(urls):
        if not os.path.isfile(url['img_file']):
            continue

        create_small_picture(url)
        
        if i % 100 == 0:
            print('{}% is finished'.format(i*100./len(urls)))


def is_empty(file):
    array = misc.imread(file)
    return np.all(array == array[0,0])


def filter_empty_imgs(dataset):
    urls = load_dataset(dataset)
    tmp = dataset + '.tmp'
    empty = 0
    with open(tmp, 'w') as f:
        for url in urls:
            file = url['img_file']
            if not os.path.isfile(file):
                empty += 1
                continue

            if is_empty(file):
                empty += 1
                continue
            
            line = dataset_item_to_str(url)
            f.write(line + '\n')
            f.flush()
        
    print('found empty pictures: ', empty)

    os.rename(tmp, dataset)
    
    
    
class UrlPopupsChecker:
    
    def __init__(self, dataset_file, img_folder, already_read):
        self.driver = create_driver()        
        self.dataset_file = dataset_file
        self.img_folder = img_folder
        self.already_read = {item['url']: True for item in already_read}
    

    def run(self):
        while True:
            url = queue.get()
            status = self.check_url(url)
            self.save_result(url, status) 
            queue.task_done()

    def save_result(self, url, status):
        if url in self.already_read:
            return
 
        to_write = dataset_item_to_str(status) + '\n'
        
        with open(self.dataset_file, 'a') as f:
            f.write(to_write)
            f.flush()

        self.already_read[url] = status


    def get_img_file(self):
        file_name = str(uuid.uuid4()) + '.png'
        return os.path.join(self.img_folder, file_name)
    
    
    def check_url(self, url):
        result = self.already_read.get(url)
        if result is not None:
            return result

        rewards = PopupRewardsCalculator()
        has_popup = False
        for _ in range(3):
            try:
                self.driver.get('http://' + url)
                has_popup = rewards.is_popup_exists(self.driver)
                break
            except:
                traceback.print_exc()
                self.driver.quit()
                self.driver = create_driver()
                continue

        img_file = self.get_img_file()
        common.scroll_to_top(self.driver)
        common.get_screenshot(self.driver, img_file)
        return {
            'url': url,
            'img_file': img_file,
            'has_popup': has_popup,
            'author': 'heuristic'
        }
        

def create_popup_dataset(dataset_file, reuse_cache = True):
    
    if os.path.isfile(dataset_file):
        return load_dataset(dataset_file)
    
    print('started creating dataset...')
        
    smoke_urls = []
    pattern = '.*((smok)|(cig)|(vap)|(tobac)).*'
    with open(resources + 'pvio_vio_us_ca_uk_sample1.csv') as f:
        rows = csv.reader(f)
        for row in rows:
            url = row[0]
            if re.match(pattern, url):
                smoke_urls.append(url)
                

    print('Found {} urls'.format(len(smoke_urls)))
    
    tmp_file = dataset_file + '.tmp'
    if os.path.isfile(tmp_file) and reuse_cache:
        processed = load_dataset(tmp_file)
        print('read from previous run cache {} urls'.format(len(processed)))
    else:
        with open(tmp_file, 'w') as f:
            pass
        processed = []

    if not os.path.isdir(img_folder):
        os.makedirs(img_folder)

    for url in smoke_urls:
        queue.put(url)

    for i in range(num_threads):
        checker = UrlPopupsChecker(tmp_file, img_folder, processed)
        t = threading.Thread(target=checker.run)
        t.daemon = True
        t.start()
    
    while True:
        size = queue.qsize()
        print('left items to process: {}'.format(size))
        if size <= 0:
            break     
        
        time.sleep(60)

    print('wait for the rest')
    queue.join()

    os.rename(tmp_file, dataset_file)
    
    return load_dataset(dataset_file)


if __name__ == '__main__':
    os.environ['DBUS_SESSION_BUS_ADDRESS'] = '/dev/null'
    extracted_popup_urls = create_popup_dataset(dataset_file)
    
    print('filtering empty images')
    filter_empty_imgs(dataset)

    print('creating small images')
    create_small_pictures(urls)

    print('processed urls: ', len(extracted_popup_urls))


