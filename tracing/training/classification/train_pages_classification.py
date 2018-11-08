import tensorflow as tf
import tensorflow.contrib.slim as slim
import tensorflow.contrib.slim.nets as nets
import nets.inception_resnet_v2
from nets.inception_resnet_v2 import inception_resnet_v2_arg_scope

import threading
import csv, re
import random
import PIL

import os
import numpy as np
import random
import sys

sys.path.append('..')
from popups.create_dataset import load_dataset as load_popup_dataset, read_small_image
from navigation.create_dataset import load_dataset as load_checkout_dataset


class PageClassifier:
    def __init__(self, session, is_training = True):
        self.session = session
        self.build_graph(is_training)
        
        self.init_task_labels_and_logits()
        
    
    def init_task_labels_and_logits(self):
        self.task_masked_logits = {
            "checkouts": tf.boolean_mask(self.checkout_logits, self.is_checkout_task), 
            "popups": tf.boolean_mask(self.popup_logits, self.is_popup_task)
        }
        
        self.task_masked_labels = {
            "checkouts": tf.boolean_mask(self.checkout_labels, self.is_checkout_task), 
            "popups": tf.boolean_mask(self.popup_labels, self.is_popup_task)
        }
        
        self.task_logits = {
            "checkouts": self.checkout_logits, 
            "popups": self.popup_logits
        }
        
        self.task_labels = {
            "checkouts": self.checkout_labels, 
            "popups": self.popup_labels,
            
        }
        
    
    def get_cross_entropy_soft_max_loss(self, logits, labels, mask):
        logits = tf.boolean_mask(logits, mask)
        labels = tf.boolean_mask(labels, mask)

        has_loss = tf.shape(logits)[0] > 0

        return tf.case({
            has_loss: (lambda: tf.nn.softmax_cross_entropy_with_logits_v2(
                labels = labels, logits = logits))
            },
            default = lambda: tf.constant(0.0)
        )
        
    
    def build_graph(self, is_training):
        with tf.device('/gpu:0'), tf.variable_scope('page_classification') as sc:
            self.dropout = tf.placeholder(tf.float32, (), "dropout")
            self.lr = tf.placeholder(tf.float32, (), "lr")
            self.l2 = tf.placeholder(tf.float32, (), "l2")

            self.img = tf.placeholder(tf.float32, (None, None, 300, 3), "img")
            self.popup_labels = tf.placeholder(tf.float32, (None, 2), "popup_labels")
            self.checkout_labels = tf.placeholder(tf.float32, (None, 2), "checkout_labels")
            
            # Bit mask detecting if it's a popups task
            self.is_popup_task = tf.placeholder(tf.bool, [None], "is_popup")
            self.is_checkout_task = tf.placeholder(tf.bool, [None], "is_checkout")
            

        with tf.device('/gpu:0'), slim.arg_scope(inception_resnet_v2_arg_scope()):
            self.net, endpoints = nets.inception_resnet_v2.inception_resnet_v2(
                   self.img, None, dropout_keep_prob = 1.0, is_training = is_training, reuse=tf.AUTO_REUSE)

            # Batch x Channels
            self.net = slim.flatten(self.net)


        with tf.variable_scope('page_classification') as sc:
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

                # Has Popup 
                with tf.variable_scope('popups'):
                    self.popup_logits = slim.fully_connected(self.flat, 2, activation_fn=None)
                    self.popup_proba = tf.nn.softmax(self.popup_logits)
                    
                    self.popup_loss = tf.reduce_mean(self.get_cross_entropy_soft_max_loss(
                        self.popup_logits, self.popup_labels, self.is_popup_task))

                # Checkout Page
                with tf.variable_scope('checkout'):
                    self.checkout_logits = slim.fully_connected(self.flat, 2, activation_fn=None)
                    self.checkout_proba = tf.nn.softmax(self.checkout_logits)
                    
                    self.checkout_loss = tf.reduce_mean(self.get_cross_entropy_soft_max_loss(
                        self.checkout_logits, self.checkout_labels, self.is_checkout_task))

            self.loss = (self.popup_loss + self.checkout_loss) / 2.0
            
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
    
    
    def make_equal(self, imgs):
        max_h = 0
        for img in imgs:
            h, _, _ = np.shape(img)
            max_h = max(max_h, h)
        
        max_h = min(1200, max_h)
        for i, img in enumerate(imgs):
            h, w, c = np.shape(img)
            if h == max_h:
                continue
            
            if h < max_h:
                to_add = np.zeros([max_h - h, w, c])
                imgs[i] = np.concatenate((img, to_add), axis=0)
            else:
                imgs[i] = img[:max_h, :, :]
            
        return imgs
    
    
    def batch_to_feed(self, batch):
        imgs = []
        
        popup_labels = []
        checkout_labels = []
        
        is_popup_task = []
        is_checkout_task = []
        
        for item in batch:
            is_popup_task.append('has_popup' in item)
            is_checkout_task.append('is_checkout' in item)
            
            if item.get('has_popup', False):
                popup_labels.append([1, 0])
            else:
                popup_labels.append([0, 1])
            
            if item.get('is_checkout', False):
                checkout_labels.append([1, 0])
            else:
                checkout_labels.append([0, 1])
            
            img = self.read_image(item)
            imgs.append(img)
        
        return {
            self.img: self.make_equal(imgs),
            self.popup_labels: popup_labels,
            self.checkout_labels: checkout_labels,
            self.is_popup_task: is_popup_task,
            self.is_checkout_task: is_checkout_task
        }
    
    
    def train(self, imgs, epochs = 10, lr = 0.001, dropout = 0.8, l2 = 0.001, batch_size=12):
        
        print('dataset size:', len(imgs))
        for epoch in range(epochs):
            print('Training started')
            random.shuffle(imgs)
            sum_loss = 0
            loss_cnts = 0
            for i, batch in enumerate(self.split(imgs, batch_size)):
                feed = self.batch_to_feed(batch)
                feed[self.lr] = lr
                feed[self.dropout] = dropout
                feed[self.l2] = l2
                
                _, loss, popup_loss, checkout_loss = self.session.run(
                    [self.train_op, self.loss, self.popup_loss, self.checkout_loss], 
                                           feed_dict = feed)
                

                sys.stdout.write('\rfinished: {:2.2f}% loss: {}, popup_loss: {}, checkout_loss: {}'
.format(i * batch_size * 100 /len(imgs), loss, popup_loss, checkout_loss))
                sys.stdout.flush()

                sum_loss += loss
                loss_cnts += 1
            
            print('Epoch finished, loss: {}'.format(sum_loss / max(loss_cnts, 1)))
            
    
    def measure(self, imgs, sample = False):
        # f1 = 2*prec*rec / (prec + rec)
        predicted_correct = {}  # task -> value
        predicted_positive = {} # task -> value
        positive = {}           # task -> value
        if sample == True:
            imgs = random.sample(imgs, 200)
        
        tasks = self.task_logits.keys()
        
        task_logits = [self.task_masked_logits[task] for task in tasks]
        task_labels = [self.task_masked_labels[task] for task in tasks]
        
        for batch in self.split(imgs, 30):
            feed = self.batch_to_feed(batch)
            feed[self.dropout] = 1.0
            
            logits_labels = self.session.run(
                task_logits + task_labels,
                feed_dict = feed)
            
            for i, task in enumerate(tasks):
                logits = logits_labels[i]
                labels = logits_labels[len(tasks) + i]
                
                predicted_batch = np.argmax(logits, -1)
                correct_batch = np.argmax(labels, -1)
                
                positive[task] = positive.get(task, 0) + np.sum(correct_batch == 0)
                predicted_positive[task] = predicted_positive.get(task, 0) + np.sum(predicted_batch == 0)

                predicted_correct_batch = np.where(correct_batch == 0, 
                                                    predicted_batch == correct_batch, 
                                                    np.full_like(correct_batch, False))
                predicted_correct[task] = predicted_correct.get(task, 0) + np.sum(predicted_correct_batch)

        result = {}
        for task in tasks:
            prec = predicted_correct.get(task, 0.) / max(predicted_positive.get(task, 0.), 1.)
            rec = predicted_correct.get(task, 0.) / max(positive.get(task, 0.), 1.)
            f1 = 2*prec*rec / max(prec + rec, 1.)
            
            result[task] = f1

        return result
    
    
    def restore_inception(self, checkpoint):
        inception_vars = tf.get_collection(
            tf.GraphKeys.GLOBAL_VARIABLES, 
            scope = 'InceptionResnetV2')

        saver = tf.train.Saver(var_list = inception_vars)
        saver.restore(self.session, checkpoint)
        

random.seed(0)

popups_dataset = load_popup_dataset('../../../resources/popups_dataset.csv', imgs_path = '../popups')
popups_dataset = list([url for url in popups_dataset if url['to_classify'] == True])
random.shuffle(popups_dataset)

split = int(len(popups_dataset) * 0.8)
train_popups = popups_dataset[:split]
test_popups = popups_dataset[split:]

print('train popups size: ', len(train_popups))
print('test popups size: ', len(test_popups))

checkouts_dataset = load_checkout_dataset('../navigation/checkout_dataset.csv', imgs_path = '../navigation')
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
#session = tf.Session()
session = tf.Session(config=tf.ConfigProto(allow_soft_placement=True, log_device_placement=False))

with tf.device('/gpu:0'):
    classifier = PageClassifier(session)
    session.run(tf.global_variables_initializer())

saver = tf.train.Saver()
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
    saver.restore(session, checkpoint)

#train_urls = train_urls
#test_urls = test_urls

for epoch in range(start_epoch, 100):
    print('epoch ', epoch)
    classifier.train(train_urls, epochs=1, lr = 0.0001, dropout = 0.75)
    train_f1 = classifier.measure(train_urls)
    print('train f1:', train_f1)
    
    test_f1 = classifier.measure(test_urls)
    print('test f1:', test_f1)
    
    saver.save(session, 'classification_model/{}'.format(epoch))

