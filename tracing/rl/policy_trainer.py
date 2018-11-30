import tensorflow as tf
from tracing.utils.dataset import *
from tracing.utils.images import ImageHelper
import random


class PolicyTrainer:
    def __init__(self, a3c):
        self.a3c = a3c

    def build_graph(self):
        self.action_label = tf.placeholder(tf.int32, (None), "action")
        self.gate_label = tf.placeholder(tf.float32, (None), "is_applied")
        self.lr = tf.placeholder(tf.float32, (), "lr")

        actions_loss = tf.nn.sparse_softmax_cross_entropy_with_logits(
            labels = self.action_label,
            logits = self.a3c.logits
        )

        self.actions_loss = tf.reduce_mean(actions_loss)

        gate_logits = tf.nn.gather(self.a3c.gate_logits, self.action_label)
        gate_loss = tf.nn.sigmoid_cross_entropy_with_logits(
            labels = self.gate_label,
            logits = gate_logits
        )
        self.gate_loss = tf.nn.reduce_mean(gate_loss)

        self.loss = self.gate_loss + self.actions_loss
        self.opt = tf.train.AdamOptimizer(lr = lr)
        self.train_op = self.opt.minimize(self.loss)

    def str2action(self, action_name):
        for i, action in enumerate(Actions.navigation):
            if action.__class__.__name__ == action_name:
                return i

        assert False, "Action {} not found among navigation actions".format(action_name)

    def trace2input(self, trace):
        images = []
        actions = []
        is_applied = []
        control_labels = []

        ih = ImageHelper()
        for item in trace:
            image_file = item['control_img']
            action = item['action']
            action_id = self.str2action(action)

            label = item['control_label']
            is_success = item['is_success']

            img = ih.read_image(image_file, 300)

            images.append(img)
            actions.append(action_id)
            is_applied.append(1. if is_success else 0.)
            control_labels.append(label)

        return {
            self.a3c.img: images,
            self.action_label: action_id,
            self.gate_label: is_applied
        }

    def group_traces(self, dataset):
        result = []
        last_domain = None
        for item in dataset:
            if item['domain'] != last_domain or item.get('control_img') is None:
                result.append([])
                last_domain = item['domain']

            if item.get('control_img'):
                result[-1].append([item])

        return result

    def train(self, items, lr = 0.0001, dropout = 0.65, epoch_start = 0, epoch_end = 10):
        print('dataset size: ', len(items))
        traces = self.group_traces(items)
        print('traces: ', len(traces))
        for epoch in range(epoch_start, epoch_end):
            print('Started training, epoch: ', epoch)
            random.shuffle(traces)

            for trace in traces:
                feed_dict = self.trace2input(trace)
                feed_dict[self.a3c.dropout] = dropout
                feed_dict[self.lr] = lr

                _, actions_loss, gate_loss = self.a3c.session.run(
                    [self.train_op, self.actions_loss, self.gate_loss],
                    feed_dict = feed_dict)


    def measure(self, items):
        raise NotImplemented()
