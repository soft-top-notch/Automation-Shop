from tracing.rl.actions import *
from tracing.rl.a3cmodel import A3CModel
from tracing.rl.rewards import PopupRewardsCalculator
from tracing.rl.environment import Environment
from tracing.rl.actor_learner import ActionsMemory
from tracing.rl.actor_learner import ActorLearnerWorker

import tensorflow as tf
import tensorflow.contrib.slim as slim
import tensorflow.contrib.slim.nets as nets
import nets.inception_resnet_v2
from nets.inception_resnet_v2 import inception_resnet_v2_arg_scope

import threading
import csv, re
import random
import PIL

import numpy as np
import random
from create_dataset import *


random.seed(0)

urls = load_dataset('../../../resources/popups_dataset.csv')
urls = list([url for url in urls if url['to_classify'] == True])
random.shuffle(urls)

split = int(len(urls) * 0.8)
train_urls = urls[:split]
test_urls = urls[split:]

print('train size: ', len(train_urls))
print('test size: ', len(test_urls))


class PopupClassifier:
    def __init__(self, session, is_training = True):
        self.session = session
        self.build_graph(is_training)
        
        
    def build_graph(self, is_training):
        with tf.variable_scope('popups_classification') as sc:
            self.dropout = tf.placeholder(tf.float32, (), "dropout")
            self.lr = tf.placeholder(tf.float32, (), "lr")
            self.l2 = tf.placeholder(tf.float32, (), "l2")

            self.img = tf.placeholder(tf.float32, (None, 300, 300, 3), "img")
            self.labels = tf.placeholder(tf.float32, (None, 2), "labels")

        with slim.arg_scope(inception_resnet_v2_arg_scope()):
            self.net, endpoints = nets.inception_resnet_v2.inception_resnet_v2(
                   self.img, None, dropout_keep_prob = 1.0, is_training = is_training, reuse=tf.AUTO_REUSE)
            # Batch x Channels
            self.net = slim.flatten(self.net)

        with tf.variable_scope('popups_classification') as sc:
            l2_reg = slim.l2_regularizer(self.l2)
            he_init = tf.contrib.layers.variance_scaling_initializer(mode="FAN_AVG")
            xavier_init = tf.contrib.layers.xavier_initializer()
            zero_init = tf.constant_initializer(0)

            with slim.arg_scope([slim.conv2d, slim.fully_connected],
                                  weights_initializer = he_init,
                                  biases_initializer = zero_init,
                                  weights_regularizer = l2_reg
                                ):
                
                self.fc2 = slim.fully_connected(self.net, 100)
                self.flat = slim.dropout(self.fc2, self.dropout, scope='dropout')

                # Popup logits
                self.logits = slim.fully_connected(self.flat, 2, activation_fn=None)
                self.proba = tf.nn.softmax(self.logits)
            
            self.loss = tf.nn.softmax_cross_entropy_with_logits_v2(labels = self.labels, 
                                                                   logits = self.logits)
            
            self.loss = tf.reduce_sum(self.loss)
            self.loss = tf.reduce_mean(self.loss)
            
            self.opt = tf.train.AdamOptimizer(self.lr)
            self.train_op = self.opt.minimize(self.loss)
    
    
    def split(self, imgs, batch_size = 10):
        batch = []
        for img in imgs:
            batch.append(img)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        if len(batch) > 0:
            yield batch
    
    
    def read_image(self, url):
        image = read_small_image(url)
        
        image = image[:, :, :3]
        [h, w, _] = image.shape
        if h < w:
            to_add = np.ndarray([w-h, w, 3], dtype=np.uint8)
            to_add.fill(0)
            image = np.append(image, to_add, axis=0)
        
        return (image -128.0) / 128.0
    
    
    def batch_to_feed(self, batch):
        labels = []
        imgs = []
        for item in batch:
            if item['has_popup']:
                labels.append([1, 0])
            else:
                labels.append([0, 1])
            
            img = self.read_image(item)
            imgs.append(img)
        
        return {
                self.img: imgs,
                self.labels: labels
            }
    
    
    def train(self, imgs, epochs = 10, lr = 0.001, dropout = 0.8, l2 = 0.001):
        for epoch in range(epochs):
            print('Training started')
            random.shuffle(imgs)
            sum_loss = 0
            loss_cnts = 0
            for batch in self.split(imgs):
                feed = self.batch_to_feed(batch)
                feed[self.lr] = lr
                feed[self.dropout] = dropout
                feed[self.l2] = l2
                
                _, loss = self.session.run([self.train_op, self.loss], feed_dict = feed)
                sum_loss += loss
                loss_cnts += 1
            
            print('Epoch finished, loss: {}'.format(sum_loss / max(loss_cnts, 1)))
            
    
    def measure(self, imgs, sample = False):
        # f1 = 2*prec*rec / (prec + rec)
        predicted_correct = 0
        predicted_positive = 0
        positive = 0
        if sample == True:
            imgs = random.sample(imgs, 200)
            
        for batch in self.split(imgs):
            feed = self.batch_to_feed(batch)
            feed[self.dropout] = 1.0

            logits = self.session.run(self.logits, feed_dict = feed)
            predicted_popups = np.argmax(logits, -1)
            correct = np.argmax(feed[self.labels], -1)
            positive += np.sum(correct == 0)
            predicted_positive += np.sum(predicted_popups == 0)
            
            predicted_correct_popups = np.where(correct == 0, 
                                                predicted_popups == correct, 
                                                np.full_like(correct, False))
            predicted_correct += np.sum(predicted_correct_popups)

        prec = predicted_correct / max(predicted_positive, 1.)
        rec = predicted_correct / max(positive, 1.)

        return 2*prec*rec / max(prec + rec, 1.)


tf.reset_default_graph()
session = tf.Session()

classifier = PopupClassifier(session)

session.run(tf.global_variables_initializer())
a3cmodel.init_from_checkpoint('inception_resnet_v2_2016_08_30.ckpt')
saver = tf.train.Saver()

checkpoint = None
start_epoch = 0
for i in range(100):
    fname = 'classification_model/{}'.format(i)
    if os.path.exists(fname + '.index'):
        checkpoint = fname
        start_epoch = i + 1

if checkpoint:
    print('loading checkpoint', checkpoint)
    saver.restore(session, checkpoint)


for epoch in range(start_epoch, 100):
    print('epoch ', epoch)
    classifier.train(train_urls, epochs=1, lr = 0.0001, dropout = 0.65)
    train_f1 = classifier.measure(train_urls)
    print('train f1:', train_f1)
    
    test_f1 = classifier.measure(test_urls)
    print('test f1:', test_f1)
    
    if epoch % 10 == 9:
        saver.save(session, 'classification_model/{}'.format(epoch))

