import random
import csv
import logging

from shop_tracer import *
from selenium_helper import *
from trace_logger import *
import common_actors
import user_data

from contextlib import contextmanager

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

# Regressioin urls for testing
test_urls = []
regression_status = []

with open('../resources/regression_urls.csv', 'r') as f:
    rows = csv.reader(f)
    for row in rows:
        url = row[0]
        status = row[1]
        if url:
            test_urls.append(url)
            regression_status.append(status)

results = []
with get_tracer(headless=False) as tracer:
    with open('url_states.csv', 'w') as f:
        for index, url in enumerate(test_urls):
            logger.info('\n\nstarted url: {}'.format(url))
            status = tracer.trace(url, 60, attempts=3, delaying_time=10)
            results.append(status)
            logger.info('finished url: {}, status: {}, state: {}'.format(url, status, status.state))
            
            if regression_status[index] == status.state:
            	f.write('{}\t{}\n'.format(url, "Exactly purchased!"))
            else:
            	f.write('{}\t{}\n'.format(url, "Can't purchased!"))
            f.flush()


states = {}
for status in results:
    if isinstance(status, ProcessingStatus):
        states[status.state] = states.get(status.state, 0) + 1

print(states)