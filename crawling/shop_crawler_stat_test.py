import random
import csv
import logging

from shop_crawler import *
from selenium_helper import *
import common_actors

from contextlib import contextmanager

# All urls
all_urls = []
with open('../resources/pvio_vio_us_ca_uk_sample1.csv', 'r') as f:
    rows = csv.reader(f)
    for row in rows:
        url = row[0]
        if url:
            all_urls.append(url)

# Random sample urls
random.seed(1)
sample_urls = random.sample(all_urls, 100)

# Some good urls to analyze by hands
good_urls = [
    'curlebotanicals.com',
    'theglamourshop.com',
    'vape-fuel.com',
    'firstfitness.com',
    'sandlakedermatology.com',
    'getwaave.com',
    'dixieems.com',
    'jonessurgical.com',
    'srandd.com',
    'ambarygardens.com',
    'anabolicwarfare.com'
]


user_info = UserInfo(
    first_name = 'John',
    last_name = 'Smith',
    country = 'United States',
    home = 34,
    street = 'Ocean drive',
    city = 'Miami',
    zip = '33125',
    state = 'FLorida',
    
    phone = '1231232',
    email = 'john@service.com'
)

billing_info = PaymentInfo(
    card_number = '1413232312312321',
    expire_date_year = 2020,
    expire_date_month = 12,
    cvc = '123'
)


selenium_path = '/home/aleksei/dist/selenium/chromedriver'

@contextmanager
def get_crawler(headless=True):
    global user_info, billing_info, selinium_path
    crawler = ShopCrawler(user_info, billing_info, selenium_path, headless=headless)
    common_actors.add_crawler_extensions(crawler)
    
    yield crawler

def get_driver(headless=True):
    global selenium_path   
    return create_chrome_driver(selenium_path, headless=headless)


logger = logging.getLogger('shop_crawler')
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler()
formatter = logging.Formatter(
        '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

results = []
with get_crawler(headless=False) as crawler:
    for url in sample_urls:
        print('\n\n{}'.format(url))
        status = crawler.crawl(url, 30)
        print(status)
        results.append(status)

states = {}
for status in results:
    if isinstance(status, ProcessingStatus):
        states[status.state] = states.get(status.state, 0) + 1
        
print(states)
