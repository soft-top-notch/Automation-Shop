from tracing.rl.rewards import PopupRewardsCalculator
from tracing.rl.environment import Environment
import threading
import csv, re
import random
import traceback


def create_popup_dataset(dataset_file, reuse_cache = True):
    import os.path
    import tracing.selenium_utils.common as common
    
    if os.path.isfile(dataset_file):
        result = []
        with open(dataset_file) as f:
            for row in f:
                url, is_popup = row.strip().split('\t')
                result.append((url, is_popup == '1'))
        return result
    
    print('started creating dataset...')
    
    def create_driver():
        for i in range(10):
            try:
                driver = common.create_chrome_driver(headless = True, size=(1280, 1024))
                driver.set_page_load_timeout(120)
                return driver
            except:
                time.sleep(2)
        
        raise Exception("can't create driver")

        
    smoke_urls = []
    pattern = '.*((smok)|(cig)|(vap)|(tobac)).*'
    with open('../../../resources/pvio_vio_us_ca_uk_sample1.csv') as f:
        rows = csv.reader(f)
        for row in rows:
            url = row[0]
            if re.match(pattern, url):
                smoke_urls.append(url)

    print('Found {} urls'.format(len(smoke_urls)))
    
    processed = 0

    tmp_file = dataset_file + '.tmp'
    mode = 'w'
    if os.path.isfile(tmp_file) and reuse_cache:
        mode = 'a'
        with open(tmp_file, 'r') as f:
            for line in f:
                processed += 1

        print('read from previous run cache {} urls'.format(processed))
    
    with open(tmp_file, mode) as f:
        driver = create_driver()
        checked_popup_urls = []
        for i, url in enumerate(smoke_urls):
            if i < processed:
                continue

            rewards = PopupRewardsCalculator()
            has_popup = False
            for _ in range(3):
                try:
                    driver.get('http://' + url)
                    has_popup = rewards.is_popup_exists(driver)
                    break
                except:
                    traceback.print_exc()
                    driver.quit()
                    driver = create_driver()
                    continue

            print(i, url, has_popup)        
            if has_popup:
                checked_popup_urls.append(url)
            
            f.write(url)
            f.write('\t')
            f.write('1' if has_popup else '0')
            f.write('\n')
            f.flush()
        
    
    os.rename(tmp_file, dataset_file)
    
    return checked_popup_urls


extracted_popup_urls = create_popup_dataset('../../../resources/popups_dataset.csv')

print('processed urls: ', len(extracted_popup_urls))


