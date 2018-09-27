from tracing.rl.actions import *
from tracing.rl.a3cmodel import A3CModel
from tracing.rl.rewards import PopupRewardsCalculator
from tracing.rl.environment import Environment
from tracing.rl.actor_learner import ActionsMemory
from tracing.rl.actor_learner import ActorLearnerWorker
import tensorflow as tf
import threading
import csv, re
import random
import os


os.environ['DBUS_SESSION_BUS_ADDRESS'] = '/dev/null'


hard_popup_urls = [
    # Choose from two options popups
    'monstervape.com',
    'twistedcigs.com',
    'ecigsejuice.com',
    'vape-fuel.com',
    'www.powervapes.net/products/',
    'ecigexpress.com',
    
    # Subscribe
    'cigarmanor.com',  #Need email or extract close button
    'smokechophouse.com',
    
    
    # Enter date popups
    'thecigarshop.com',
    'cigartowns.com',
    'docssmokeshop.com',
    'enhancedecigs.com',
    'betamorphecigs.com',
    
    # Accept Cookie
    'theglamourshop.com',
    'smokingvaporstore.com',
    
    
]

no_popup_urls = [
    'dixieems.com',
    'firstfitness.com',
    'sandlakedermatology.com',
    'dixieems.com',
    'anabolicwarfare.com',
    'jonessurgical.com',
    'srandd.com'
]


def create_popup_dataset(dataset_file):
    import os.path
    import tracing.selenium_utils.common as common
    
    if os.path.isfile(dataset_file):
        result = []
        with open(dataset_file) as f:
            for row in f:
                url, is_popup = row.strip().split('\t')
                result.append((url, is_popup == '1'))
        return result
    
    print('started creating dataset...')
    
    def create_driver():
        for i in range(10):
            try:
                return common.create_chrome_driver(headless = True, size=(1280, 1024))
            except:
                time.sleep(2)
        
        raise Exception("can't create driver")
    
    smoke_urls = []
    pattern = '(smok)|(cig)|(vape)|(tobac)'
    with open('../../resources/pvio_vio_us_ca_uk_sample1.csv') as f:
        rows = csv.reader(f)
        for row in rows:
            url = row[0]
            if re.match(pattern, url):
                smoke_urls.append(url)

    print('Found {} urls'.format(len(smoke_urls)))
    
    tmp_file = dataset_file + '.tmp'
    with open(tmp_file, 'w') as f:
    
        driver = create_driver()
        checked_popup_urls = []
        for i, url in enumerate(smoke_urls):
            rewards = PopupRewardsCalculator()
            has_popup = False
            for _ in range(3):
                try:
                    driver.get('http://' + url)
                    has_popup = rewards.is_popup_exists(driver)
                    break
                except:
                    traceback.print_exc()
                    driver.quit()
                    driver = create_driver()
                    continue

            print(i, url, has_popup)        
            if has_popup:
                checked_popup_urls.append(url)
            
            f.write(url)
            f.write('\t')
            f.write('1' if has_popup else '0')
            f.write('\n')
            f.flush()
        
    
    os.rename(tmp_file, dataset_file)
    
    return checked_popup_urls

extracted_popup_urls = create_popup_dataset('popups_dataset.csv')

popup_urls = list([url for (url, is_popup) in extracted_popup_urls if is_popup==True])
random.shuffle(popup_urls)

split = int(len(popup_urls) * 0.8)
train_urls = popup_urls[:split]
test_urls = popup_urls[split:]


tf.reset_default_graph()
session = tf.Session()

num_workers = 8

global_model = A3CModel(len(Actions.actions), session = session, train_deep = False)
session.run(tf.global_variables_initializer())
global_model.init_from_checkpoint('inception_resnet_v2_2016_08_30.ckpt')

workers = []

for i in range(num_workers):
    env = Environment(PopupRewardsCalculator(), user={}, headless=True)
    worker = ActorLearnerWorker("worker-{}".format(i),
                                train_urls,
                                global_model, 
                                env, 
                                1000, 
                                n_step = 10, 
                                lr=0.001, 
                                l2 = 0.03,
                                entropy_l=0.2, 
                                dropout = 0.8, 
                                gamma=0.99)
    workers.append(worker)
    
coord = tf.train.Coordinator()

import numpy as np

def start(worker):
    while True:
        try:
            if ActorLearnerWorker.global_step < worker.max_steps:
                worker.run()
            else:
                return
        except:
            traceback.print_exc()
        
checkpoint = None
for i in range(100):
    fname = './checkpoint-{}'.format(i)
    if os.path.exists(fname):
        checkpoint = fname

if checkpoint:
    print('loading checkpoint', checkpoint)
    global_model.restore(checkpoint)

threads = []
for worker in workers:
    thread = threading.Thread(target=lambda: start(worker))
    thread.daemon = True 
    thread.start()
    threads.append(thread)


saved = {}
while True:
    time.sleep(60)
    
    rewards = ActorLearnerWorker.step_rewards[:]
    steps = len(rewards)
    if steps > 0:
        print('\n\n-----> avg_reward {} after {} steps\n\n'.format(sum(rewards) / steps, steps))

    portion = steps // 30
    if portion > 0 and saved.get(portion) is None:
        print('saving model', portion)
        global_model.save('./checkpoint-{}'.format(portion))
        saved[portion] = True
    
coord.join(threads)
