import random
import csv
import logging

from shop_tracer import *
from selenium_helper import *
import common_actors
import user_data

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
random.seed(4)
sample_urls = random.sample(all_urls, 500)

# Some good urls to analyze by hands
good_urls = [
    'docssmokeshop.com',
    'vapininthecape.com',
    'jonessurgical.com',
    'vaporsupply.com',
    'firstfitness.com',
    'srandd.com',
    'theglamourshop.com',
    'sandlakedermatology.com',
    'docssmokeshop.com',
    'dixieems.com',
    'srandd.com',
    'ambarygardens.com',
    'anabolicwarfare.com'
]


selenium_path = '/usr/bin/chromedriver'

@contextmanager
def get_tracer(headless=False):
    global selinium_path
    tracer = ShopTracer(user_data.get_user_data, selenium_path, headless=headless)
    common_actors.add_tracer_extensions(tracer)

    yield tracer


logger = logging.getLogger('shop_tracer')
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
formatter = logging.Formatter(
        '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

results = []
with get_tracer(headless=False) as tracer:
    with open('url_states.csv', 'a') as f:
        for url in sample_urls:
            logger.info('\n\nstarted url: {}'.format(url))
            status = tracer.trace(url, 60, attempts=1)
            results.append(status)
            logger.info('finished url: {}, status: {}, state: {}'.format(url, status, status.state))
            
            f.write('{}\t{}\n'.format(url, status.state))
            f.flush()


states = {}
for status in results:
    if isinstance(status, ProcessingStatus):
        states[status.state] = states.get(status.state, 0) + 1

print(states)
