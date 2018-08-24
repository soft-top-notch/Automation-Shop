import random
import csv
import logging

from shop_tracer import *
from selenium_helper import *
from trace_logger import *
import common_actors
import user_data

from contextlib import contextmanager

# All urls
all_urls = []
with open('../resources/regression_urls.csv', 'r') as f:
    rows = csv.reader(f)
    for row in rows:
        url = row[0]
        if url:
            all_urls.append(url)
# Random sample urls
random.seed(4)
# sample_urls = random.sample(all_urls, 100)

# Some good urls to analyze by hands
good_urls = [
    'naturesbestrelief.com',
    'purekindbotanicals.com',
    'ossur.com',
    'freshfarmscbd.com',
    'naturesbestrelief.com',
    'www.poundsandinchesaway.com',
    'bluespringsanimalhospital.com',
    'mikestvbox.com',
]

trace_logger = FileTraceLogger("images", "checkout_page_filling")

@contextmanager
def get_tracer(headless=False):
    tracer = ShopTracer(user_data.get_user_data, headless=headless, trace_logger=trace_logger)
    common_actors.add_tracer_extensions(tracer)

    yield tracer


logger = logging.getLogger('shop_tracer')
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
formatter = logging.Formatter(
        '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# ToDo remove before merge
import csv

urls_to_test = []
with open('../resources/url_states.csv') as f:
    reader = csv.reader(f, delimiter='\t', quotechar='\\')
    for row in reader:
        url, status = row
        if status == "checkout_page" or status == "purchased":
            urls_to_test.append(url)

results = []
with get_tracer(headless=False) as tracer:
    with open('url_states.csv', 'w') as f:
        for url in all_urls:
            logger.info('\n\nstarted url: {}'.format(url))
            status = tracer.trace(url, 60, attempts=3, delaying_time=10)
            results.append(status)
            logger.info('finished url: {}, status: {}, state: {}'.format(url, status, status.state))
            
            f.write('{}\t{}\n'.format(url, status.state))
            f.flush()


states = {}
for status in results:
    if isinstance(status, ProcessingStatus):
        states[status.state] = states.get(status.state, 0) + 1

print(states)
