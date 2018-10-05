from tracing.rl.actions import *
from tracing.rl.a3cmodel import A3CModel
from tracing.rl.rewards import PopupRewardsCalculator
from tracing.rl.environment import Environment
from tracing.rl.actor_learner import ActionsMemory
from tracing.rl.actor_learner import ActorLearnerWorker
import tensorflow as tf
import tensorflow.contrib.slim as slim

import threading
import csv, re
import random
import PIL

import numpy as np

from create_dataset import *

urls = load_dataset('../../../resources/popups_dataset.csv')

urls = list([url for url in urls if url['to_classify'] == True])
random.shuffle(urls)

split = int(len(urls) * 0.8)
train_urls = urls[:split]
test_urls = urls[split:]

print('train size: ', len(train_urls))
print('test size: ', len(test_urls))


class PopupClassifier:
    def __init__(self, a3c_model):
        self.a3c_model = a3c_model
        self.session = self.a3c_model.session
        self.build_graph()
        
        
    def build_graph(self):
        with tf.variable_scope('popups_classification') as sc:
            self.labels = tf.placeholder(tf.float32, (None, 2), "img")
            self.lr = tf.placeholder(tf.float32, (), "lr")
            self.dropout = tf.placeholder(tf.float32, (), "dropout")
            self.l2 = tf.placeholder(tf.float32, (), "l2")
            
            l2_reg = slim.l2_regularizer(self.l2)
            he_init = tf.contrib.layers.variance_scaling_initializer(mode="FAN_AVG")
            xavier_init = tf.contrib.layers.xavier_initializer()
            zero_init = tf.constant_initializer(0)

            with slim.arg_scope([slim.conv2d, slim.fully_connected],
                                  weights_initializer = he_init,
                                  biases_initializer = zero_init,
                                  weights_regularizer = l2_reg
                                ):
                
                self.fc2 = slim.fully_connected(self.a3c_model.net, 100)
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
                self.a3c_model.img: imgs,
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

a3cmodel = A3CModel(len(Actions.actions), session = session, train_deep = False)
classifier = PopupClassifier(a3cmodel)

session.run(tf.global_variables_initializer())
a3cmodel.init_from_checkpoint('inception_resnet_v2_2016_08_30.ckpt')


for epoch in range(60):
    print('epoch ', epoch)
    classifier.train(train_urls, epochs=1)
    train_f1 = measure(classifier, train_urls)
    print('train f1:', train_f1)
    
    test_f1 = measure(classifier, test_urls)
    print('test f1:', test_f1)


saver = tf.train.Saver()
saver.save(self.session, 'classification_model')
