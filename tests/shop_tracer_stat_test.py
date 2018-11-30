import random
import csv
import logging
from queue import Queue
import threading
import time
from contextlib import contextmanager


from tracing.shop_tracer import *
import tracing.trace_logger as trace_logger
import tracing.common_actors as common_actors
import tracing.user_data as user_data
from tracing.status import *


num_threads = 8 # Number of threads to run
num_urls = 100  # Number of urls to sample 
delay = 5 # Seconds to sleep after every action in Selenium

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
sample_urls = random.sample(all_urls, num_urls)

@contextmanager
def get_tracer(headless, processer_num = 0):
    logger = trace_logger.FileTraceLogger('log/results_{}.jsonl'.format(processer_num), 
                                              'log/images_{}'.format(processer_num))
    tracer = ShopTracer(user_data.get_user_data, headless=headless, trace_logger = logger)
    common_actors.add_tracer_extensions(tracer)

    yield tracer


logger = logging.getLogger('shop_tracer')
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
formatter = logging.Formatter(
        '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

results = {}
def save_result(url, status):
    with open('url_states.csv', 'a') as f:
        f.write('{}\t{}\n'.format(url, status.state))
        
    results[url] = status

class Processor:
    def __init__(self, processor_num):
        self.processor_num = processor_num
        
    def process(self):
        with get_tracer(False, self.processor_num) as tracer:
            while True:
                url = queue.get()
                status = tracer.trace(url, attempts=3, delaying_time=delay)
                save_result(url, status)        

os.environ['DBUS_SESSION_BUS_ADDRESS'] = '/dev/null'

for i in range(8):
    processor = Processor(i)
    t = threading.Thread(target=processor.process)
    t.daemon = True
    t.start()

start = time.time()

for url in sample_urls:
    queue.put(url)
    
while len(results) < num_urls:
    print('finished: {}'.format(len(results)))
    time.sleep(15)

print("Execution time = {0:.5f}".format(time.time() - start))    

states = {}
for status in results.values():
    state = status.state or "None"
    states[state] = states.get(state, 0) + 1

print(states)
