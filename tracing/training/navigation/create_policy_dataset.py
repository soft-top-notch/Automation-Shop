from contextlib import contextmanager
from create_classification_dataset import CheckoutsDataset
from tracing.utils.downloader import Downloader
import tracing.heuristic.common_actors as common_actors
from tracing.heuristic.shop_tracer import ShopTracer
from tracing.rl.environment import Environment
import logging
import threading
from actions_saver import ActionsFileRecorder
from queue import Queue
import time
import traceback
import os, os.path
import json

threads = 4

@contextmanager
def get_tracer(headless=True):
    env = Environment(headless=headless, max_passes=10)
    tracer = ShopTracer(environment = env)
    common_actors.add_tracer_extensions(tracer)
    yield tracer


logger = logging.getLogger('shop_tracer')
logger.setLevel(logging.WARN)

handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


downloader = Downloader()
dataset_file = downloader.download_checkout_dataset()
checkout_dataset = CheckoutsDataset.read(dataset_file)

domains = set()


for item in checkout_dataset.items:
    if item['state'].startswith('checkout') or item['state'] == 'purchased':
        domains.add(item['domain'])

queue = Queue()
for url in domains:
    queue.put(url)


dataset_file = 'policy_dataset'
processed_domains = []

# Check already processed domains
meta_file = os.path.join(dataset_file, 'meta.jsonl')

if os.path.exists(meta_file):
    with open(meta_file) as f:
        for row in f:
            info = json.loads(row)
            domain = info['domain']
            if domain not in processed_domains:
                processed_domains.append(domain)

class Processor:
    def process(self):
        global results, queue, dataset_file, processed_domains

        with get_tracer(True) as tracer:
            tracer.add_listener(ActionsFileRecorder(dataset_file))
            while True:
                url = queue.get()
                if url not in processed_domains:
                    try:
                        tracer.trace(url, attempts=1, delaying_time=60)
                        processed_domains.append(url)
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


while len(processed_domains) < len(domains):
    print('\n\nfinished: {}\n\n'.format(len(processed_domains)))
    time.sleep(60)

