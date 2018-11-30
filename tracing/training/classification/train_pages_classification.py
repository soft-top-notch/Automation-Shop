import tensorflow as tf

import os
import random
from tracing.utils.downloader import Downloader

from tracing.training.navigation.create_dataset import CheckoutsDataset
from tracing.training.popups.create_dataset import PopupsDataset
from tracing.training.classification.page_classifier import PageClassifier


random.seed(0)

# Change it to your cache folder
downloader = Downloader()
popups_dataset_file = downloader.download_popup_dataset()
checkouts_dataset_file = downloader.download_checkout_dataset()

popups_dataset = PopupsDataset.read(popups_dataset_file).items
popups_dataset = list([url for url in popups_dataset if url['to_classify'] == True])
random.shuffle(popups_dataset)

split = int(len(popups_dataset) * 0.8)
train_popups = popups_dataset[:split]
test_popups = popups_dataset[split:]

print('train popups size: ', len(train_popups))
print('test popups size: ', len(test_popups))

checkouts_dataset = CheckoutsDataset.read(checkouts_dataset_file).items
random.shuffle(checkouts_dataset)

split = int(len(checkouts_dataset) * 0.8)
train_checkouts = checkouts_dataset[:split]
test_checkouts = checkouts_dataset[split:]

print('train checkouts size: ', len(train_checkouts))
print('test checkouts size: ', len(test_checkouts))

train_urls = train_popups + train_checkouts
test_urls = test_popups + test_checkouts

random.shuffle(train_urls)
random.shuffle(test_urls)


tf.reset_default_graph()
session = tf.Session(config=tf.ConfigProto(allow_soft_placement=True, log_device_placement=False))

with tf.device('/gpu:0'):
    classifier = PageClassifier(session, use_batch_norm = False)
    session.run(tf.global_variables_initializer())

classifier.restore_inception('./inception_resnet_v2_2016_08_30.ckpt')

checkpoint = None
start_epoch = 0
for i in range(100):
    fname = 'classification_model/{}'.format(i)
    if os.path.exists(fname + '.index'):
        checkpoint = fname
        start_epoch = i + 1

if checkpoint:
    print('loading checkpoint', checkpoint)
    classifier.load(checkpoint)


for epoch in range(start_epoch, 20):
    print('epoch ', epoch)
    classifier.train(train_urls, epochs=1, lr = 0.0001, dropout = 0.65)
    train_f1 = classifier.measure(train_urls)
    print('train f1:', train_f1)
    
    test_f1 = classifier.measure(test_urls)
    print('test f1:', test_f1)
    
    classifier.save('classification_model/{}'.format(epoch))

