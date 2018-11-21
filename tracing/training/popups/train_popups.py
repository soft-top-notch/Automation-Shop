from tracing.rl.actions import *
from tracing.rl.a3cmodel import A3CModel
from tracing.rl.rewards import *
from tracing.rl.environment import Environment
from tracing.rl.actor_learner import ActorLearnerWorker
import tensorflow as tf
import threading
import random

from create_dataset import read_popups_rl_dataset
from tracing.training.classification.page_classifier import PageClassifier


os.environ['DBUS_SESSION_BUS_ADDRESS'] = '/dev/null'

resources = '../../../resources'
dataset_file = resources + '/popups_dataset.csv'

pretrained_checkpoint = '../pretrain/checkpoints/pretrain_checkpoint-10'

assert os.path.isfile(dataset_file), 'Dataset file {} is not exists'.format(dataset_file)


urls = read_popups_rl_dataset(dataset_file)

popup_urls = list([status['url'] for status in urls if status['has_popup']==True])
random.shuffle(popup_urls)

split = int(len(popup_urls) * 0.8)
train_urls = popup_urls[:split]
test_urls = popup_urls[split:]

print('train size: ', len(train_urls))
print('test size: ', len(test_urls))


g1 = tf.Graph()
with g1.as_default():
    page_classifier = PageClassifier.get_pretrained('/home/aleksei/work/projects/g2/cache')


tf.reset_default_graph()
session = tf.Session()

num_workers = 16

# Do input Birth Day, Month, Year and Email
# Do it for training Speedup
fixed_probas = {0: 1., 1: 1., 2: 1., 4: 1.}

global_model = A3CModel(len(Actions.actions), session = session, train_deep = True, fixed_gate_probas = fixed_probas)
session.run(tf.global_variables_initializer())
if pretrained_checkpoint:
    saver = tf.train.Saver()
    saver.restore(session, pretrained_checkpoint)

workers = []

for i in range(num_workers):
    env = Environment(PageRewardsCalculator.for_popups(page_classifier), user={}, headless=True)
    worker = ActorLearnerWorker("worker-{}".format(i),
                                train_urls,
                                global_model, 
                                env, 
                                100, 
                                n_step = 10, 
                                lr=0.001, 
                                l2 = 0.003,
                                entropy_l=0.1, 
                                dropout = 0.8, 
                                gamma=0.99)
    workers.append(worker)
    
coord = tf.train.Coordinator()

def start_learning(worker):
    while True:
        try:
            if ActorLearnerWorker.global_step + 1 < worker.max_steps:
                worker.run()
            else:
                return
        except:
            traceback.print_exc()
        
checkpoint = None
for i in range(100):
    fname = './checkpoints/checkpoint-{}'.format(i)
    if os.path.exists(fname + '.index'):
        checkpoint = fname

if checkpoint:
    print('loading checkpoint', checkpoint)
    global_model.restore(checkpoint)

threads = []
for worker in workers:
    thread = threading.Thread(target=lambda: start_learning(worker))
    thread.daemon = True 
    thread.start()
    threads.append(thread)


saved = {}
while ActorLearnerWorker.global_step + 1 < workers[0].max_steps:
    time.sleep(60)
    
    rewards = ActorLearnerWorker.step_rewards[:]
    steps = len(rewards)
    if steps > 0:
        print('\n\n-----> avg_reward {} after {} steps\n\n'.format(sum(rewards) / steps, steps))

    portion = steps // 100
    if portion > 0 and saved.get(portion) is None:
        print('saving model', portion)
        global_model.save('./checkpoints/checkpoint-{}'.format(portion))
        saved[portion] = True
    
coord.join(threads)


closed = 0
tested = 0

errors = []

def start_acting(worker):
    global closed, tested, errors

    while True:
        url = queue.get()
        reward = worker.act(url)
        if reward is None:
            continue


        tested += 1
        if reward > 0:
            closed += 1
        else:
            errors.append(url)

        queue.task_done()


queue = Queue()
for url in test_urls:
    queue.put(url)

print('Started quality measurement')


for worker in workers:
    thread = threading.Thread(target=lambda: start_acting(worker))
    thread.daemon = True
    thread.start()
    threads.append(thread)

while queue.qsize() > 0:
    time.sleep(60)

    if tested > 0:
        print('\n\n-----> quality {} after {} steps\n\n'.format(closed/tested, tested))


coord.join(threads)

print('Finished quality measurement')
print('Not closed urls:')
for url in errors:
    print(url)

print('\n\nquality: {}, steps: {}'.format(closed / tested, tested))

