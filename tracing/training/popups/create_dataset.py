from tracing.rl.rewards import HeuristicPopupRewardsCalculator
import tracing.selenium_utils.common as common

import threading
import csv, re
import traceback
import time
import os.path
import uuid
from queue import Queue
from tracing.utils.dataset import *


num_threads = 8
queue = Queue()
resources = '../../../resources/'
dataset_path = 'popups_dataset'


def dataset_item_to_str(item):
    return '{}\t{}\t{}\t{}\t{}'.format(
        item['url'],
        item['has_popup'],
        item['img_file'],
        item['author'],
        item.get('to_classify', True)
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

def read_popups_rl_dataset(file):
    result = []
    with open(file, 'r') as f:
        for row in f:
            item = str_to_dataset_item(row.strip())
            if item:
                result.append(item)

    return result


class PopupsDataset(IDataset):
    def __init__(self, items = None, file = None):
        super().__init__(items, file)

    def line2item(self, str):
        item = str_to_dataset_item(str)
        if "img_file" in item:
            return item

        return None

    def item2line(self, item):
        return dataset_item_to_str(item)

    @staticmethod
    def read(file):
        return PopupsDataset(file=file)


def create_driver():
    for i in range(10):
        try:
            driver = common.create_chrome_driver(headless = True, size=(1280, 1024))
            driver.set_page_load_timeout(120)
            return driver
        except:
            time.sleep(2)
        
    raise Exception("can't create driver")


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

        rewards = HeuristicPopupRewardsCalculator()
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
        

def create_popup_dataset(dataset_path, reuse_cache = True):
    
    if os.path.isdir(dataset_path):
        return PopupsDataset.read(dataset_path)

    print('started creating dataset...')
        
    smoke_urls = []
    pattern = '.*((smok)|(cig)|(vap)|(tobac)).*'
    with open(resources + 'pvio_vio_us_ca_uk_sample1.csv') as f:
        rows = csv.reader(f)
        cnt = 0
        for row in rows:
            url = row[0]
            if re.match(pattern, url):
                smoke_urls.append(url)
                cnt += 1
                if cnt > 100:
                    break

    print('Found {} urls'.format(len(smoke_urls)))
    
    tmp_path = dataset_path + '.tmp'
    img_folder = os.path.join(tmp_path, 'imgs')
    dataset_file = os.path.join(tmp_path, "meta.csv")

    if os.path.isdir(tmp_path) and reuse_cache:
        processed = PopupsDataset.read(tmp_path)
        print('read from previous run cache {} urls'.format(len(processed.items)))
    else:
        os.mkdir(tmp_path)
        os.mkdir(img_folder)
        open(dataset_file, 'w').close()
        processed = []

    if not os.path.isdir(img_folder):
        os.makedirs(img_folder)

    for url in smoke_urls:
        queue.put(url)

    for i in range(num_threads):
        checker = UrlPopupsChecker(dataset_file, img_folder, processed)
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

    os.rename(tmp_path, dataset_path)
    
    return PopupsDataset.read(dataset_path)


if __name__ == '__main__':
    os.environ['DBUS_SESSION_BUS_ADDRESS'] = '/dev/null'
    dataset = create_popup_dataset(dataset_path)

    print('filtering empty images')
    dataset.filter_empty_imgs()

    print('creating small images')
    dataset.create_small_pictures(width = 300)

    dataset.save()

    print('processed urls: ', len(dataset.items))


