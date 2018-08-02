import random
import csv
import logging

from shop_crawler import *
from selenium_helper import *
import common_actors
from analyzing_checkout import CheckoutUrlsInfo

from contextlib import contextmanager

# All urls
all_urls = []
with open('../resources/url_states.csv', 'r') as f:
    rows = csv.reader(f)
    for row in list(rows):
        url_list = row[0].split("\t")
        if url_list[1] == "checkout_page" or url_list[1] == "purchased":
            all_urls.append(url_list[0])

# Random sample urls
random.seed(4)
sample_urls = random.sample(all_urls, 5)

# Some good urls to analyze by hands
good_urls = [
    'spotofdelight.com',
    'anthonyscigars.com',
    'whatsmyscent.com',
    'musclesoft.com',
    'cbdevangelist.com',
    'siskiyouseeds.com',
    'nombaone.com',
    'naturesbestrelief.com',
    'nutrastore.com',
    'theexpressdiabetic.com',
    'pradopaintingcorp.com',
    'baypointedermatology.com',
    'jamesmedical.net',
    'earthlymist.com',
    'melandrose.com',
    'larofarms.com',
    'triumphlifesavers.com',
    'dixieems.com',
    'thecandygiftbasket.com',
    'herbalcafeorganics.com',
    'flamme.us',
    'reelsmokers.net',
    'www.communitysurgical.com',
    'anabolicwarfare.com',
    'firstfitness.com',
    'theglamourshop.com',
    'sandlakedermatology.com',
    'getwaave.com',
    'jonessurgical.com'
]
user_info = UserInfo(
    first_name = 'John',
    last_name = 'Smith',
    country = 'United States',
    company_name = 'Jacky',
    home = 34,
    street = 'Ocean drive',
    city = 'Miami',
    zip = '33125',
    state = 'Florida',
    phone = '1231232',
    email = 'john@service.com',
    password = 'Jacky123'
)

billing_info = PaymentInfo(
    card_number = '1413232312312321',
    card_name = 'Visa Card',
    card_type = 'Visa',
    expire_date_year = 2020,
    expire_date_month = 12,
    cvc = '123'
)


selenium_path = '/usr/bin/chromedriver'

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
url_analyzer = CheckoutUrlsInfo()

with get_crawler(headless=False) as crawler:
    for url in all_urls:
        logger.info('\n\nstarted url: {}'.format(url))
        crawler.init_analyzer(url_analyzer)
        status = crawler.crawl(url, 60, attempts=1)
        results.append(status)
        logger.info('finished url: {}, status: {}, state: {}'.format(url, status, status.state))

url_analyzer.analyze_result()
states = {}
for status in results:
    if isinstance(status, ProcessingStatus):
        states[status.state] = states.get(status.state, 0) + 1

print(states)
