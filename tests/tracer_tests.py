import random
import csv
import logging
import sys

sys.path.insert(0, '../tracing')

import heuristic.common_actors as common_actors
import user_data

from rl.environment import *
from heuristic.shop_tracer import *
from trace_logger import *
from datetime import datetime
from contextlib import contextmanager


@contextmanager
def get_tracer(headless=True):
    env = Environment(headless=headless, max_passes=10)
    tracer = ShopTracer(environment = env, get_user_data = user_data.get_user_data)
    common_actors.add_tracer_extensions(tracer)

    yield tracer

logger = logging.getLogger('shop_tracer')
logger.propagate = False
logger.setLevel(logging.INFO)

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

date_format = "%m-%d-%Y %H:%M:%S"
results = []
times = []

with get_tracer(headless=True) as tracer:
    for index, url in enumerate(test_urls):
        print('\n\nstarted url: {}'.format(url))
        old_time = datetime.now()
        status = tracer.trace(url, 60, attempts=1, delaying_time=2)
        new_time = datetime.now()

        if status.state == States.purchased:
            logger.warning("\n\nfinished url: {}, status: {}, state: {}"
                           .format(url, status, "-----Exactly purchased! Success!-----"))
        else:
            warnning_text = "\n\nfinished url: {}, status: {}, state: {}"\
                .format(url, status, "-----Can't purchase! Failed!-----")
            logger.warning(warnning_text)
            results.append(warnning_text)
        logger.warning("\n\n-------Execute time: {} minutes-------".format(int((new_time - old_time).total_seconds() / 60.0)))
        times.append(int((new_time - old_time).total_seconds() / 60.0))

logger.warning("\n\n-------Average time: {} minutes-------".format(sum(times) / len(times)))

with open("time.csv", "w") as f:
    for ind, url in enumerate(test_urls):
        f.write('{}\t{}\n'.format(url, times[ind]))
    f.write('{}\t{}\n'.format("Average time", sum(times) / len(times)))

if not results:
    print("All are succeeded!")
else:
    for failure in results:
        print(failure)
    sys.exit("Failed!")