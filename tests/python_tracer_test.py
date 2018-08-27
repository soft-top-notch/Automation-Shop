import random
import csv
import logging
import sys

sys.path.insert(0, '../tracing')

from shop_tracer import *
from selenium_helper import *
from trace_logger import *
import common_actors
import user_data

from contextlib import contextmanager

@contextmanager
def get_tracer(headless=False):
    tracer = ShopTracer(user_data.get_user_data, headless=headless)
    common_actors.add_tracer_extensions(tracer)

    yield tracer


logger = logging.getLogger('shop_tracer')
logger.setLevel(logging.WARNING)

handler = logging.StreamHandler()
formatter = logging.Formatter(
        '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Regressioin urls for testing
test_urls = []

with open('regression_urls.csv', 'r') as f:
    rows = csv.reader(f)
    for row in rows:
        url = row[0]
        status = row[1]
        if url:
            test_urls.append(url)

results = []
with get_tracer(headless=False) as tracer:
    for index, url in enumerate(test_urls):
        print('\n\nstarted url: {}'.format(url))
        status = tracer.trace(url, 60, attempts=3, delaying_time=10)

        if status.state == States.purchased:
            logger.warning('\n\nfinished url: {}, status: {}, state: {}'.format(url, status, "-----Exactly purchased! Success!-----"))
        else:
            warnning_text = '\n\nfinished url: {}, status: {}, state: {}'.format(url, status, "-----Can't purchase! Failed!-----")
            logger.warning(warnning_text)
            results.append(warnning_text)


if not results:
    print("All are succeeded!")
else:
    for failure in results:
        print(failure)
    sys.exit("Failed!")