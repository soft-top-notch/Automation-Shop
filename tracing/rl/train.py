from tracing.rl.actions import *
from tracing.rl.a3cmodel import A3CModel
from tracing.rl.rewards import PopupRewardsCalculator
from tracing.rl.environment import Environment
from tracing.rl.actor_learner import ActorLearnerWorker
import tensorflow as tf
import threading

popup_urls = [
    # Choose from two options popups
    'monstervape.com',
    'twistedcigs.com',
    'ecigsejuice.com',
    'vape-fuel.com',
    'powervapes.net',
    'ecigexpress.com',
    'ecigvaporstore.com',
    
    # Subscribe
    'cigarmanor.com',
    
    # Enter date popups
    'thecigarshop.com',
    'cigartowns.com',
    'docssmokeshop.com',
    'enhancedecigs.com',
    'betamorphecigs.com',
    
    # Accept Cookie
    'theglamourshop.com'
]


tf.reset_default_graph()
session = tf.Session()

num_workers = 16

global_model = A3CModel(len(Actions.actions), session = session)
workers = []

for i in range(num_workers):
    env = Environment(PopupRewardsCalculator(), user={}, headless=True)
    workers.append(ActorLearnerWorker("worker-{}".format(i), popup_urls, global_model, env, 1000))

coord = tf.train.Coordinator()
session.run(tf.global_variables_initializer())


%matplotlib inline
import numpy as np
import matplotlib.pyplot as plt

threads = []
for worker in workers:
    thread = threading.Thread(target=lambda: worker.run())
    thread.start()
    threads.append(thread)

while True:
    time.sleep(30)
    
    rewards = ActorLearnerWorker.step_rewards[:]
    if len(rewards) > 0:
        print('\n\n\n\navg_reward:', sum(rewards) / len(rewards))
        print('\n\n\n\n')
    
coord.join(threads)


