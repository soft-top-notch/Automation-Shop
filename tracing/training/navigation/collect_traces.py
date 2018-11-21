from tracing.shop_tracer import *
import tracing.trace_logger as trace_logger
import tracing.common_actors as common_actors
import tracing.user_data as user_data
import threading
from queue import Queue
import csv
from contextlib import contextmanager
import os.path
import traceback


threads = 8
num_urls = 10000
status_file = 'url_states.csv'  # States where tracer stopped for every url
delay = 5

random.seed(0)  # Fix dataset

all_urls = []
with open('../../../resources/pvio_vio_us_ca_uk_sample1.csv', 'r') as f:
    rows = csv.reader(f)
    for row in rows:
        url = row[0]
        if url:
            all_urls.append(url)

url_to_trace = random.sample(all_urls, num_urls)


@contextmanager
def get_tracer(headless):
    logger = trace_logger.FileTraceLogger('log/results.jsonl',
                                          'log/images',
                                          clear=False)
    tracer = ShopTracer(user_data.get_user_data, headless=headless, trace_logger=logger)
    common_actors.add_tracer_extensions(tracer)

    yield tracer


logger = logging.getLogger('shop_tracer')
logger.setLevel(logging.WARN)

handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Read previous statuses
results = {}
if os.path.isfile(status_file):
    with open(status_file, 'r') as f:
        for line in f:
            url, status = line.split('\t')
            results[url] = status
else:
    with open(status_file, 'w'):
        pass


queue = Queue()
for url in url_to_trace:
    queue.put(url)


class Processor:

    @staticmethod
    def save_result(url, status):
        global results, status_file

        line = '{}\t{}\n'.format(url, status.state)
        with open(status_file, 'a') as f:
            f.write(line)
            f.flush()

        results[url] = status

    def process(self):
        global results

        with get_tracer(True) as tracer:
            while True:
                url = queue.get()
                if url not in results:
                    try:
                        status = tracer.trace(url, attempts=1, delaying_time=delay)
                        Processor.save_result(url, status)
                    except:
                        print('\n\nhigh level exception:')
                        traceback.print_exc()
                        continue

                queue.task_done()


for _ in range(threads):
    processor = Processor()
    t = threading.Thread(target=processor.process)
    t.daemon = True
    t.start()


while len(results) < num_urls:
    print('\n\nfinished: {}\n\n'.format(len(results)))
    time.sleep(60)
