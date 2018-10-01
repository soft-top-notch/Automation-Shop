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


num_threads = 8
resources = '../../../resources/'
queue = Queue()
dataset_file = resources + 'popups_dataset.csv'
img_folder = 'popups_dataset_imgs/'


def dataset_item_to_str(item):
    return '{}\t{}\t{}\t{}'.format(item['url'], item['has_popup'], item['img_file'], item['author'])


def str_to_dataset_item(line):
    parts = line.split('\t')
    return {
       'url': parts[0],
       'has_popup': parts[1],
       'img_file': parts[2],
       'author': parts[3]
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


os.environ['DBUS_SESSION_BUS_ADDRESS'] = '/dev/null'
extracted_popup_urls = create_popup_dataset(dataset_file)

print('processed urls: ', len(extracted_popup_urls))


