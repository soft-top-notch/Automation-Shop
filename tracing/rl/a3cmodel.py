import tensorflow as tf
import tensorflow.contrib.slim as slim
import tensorflow.contrib.slim.nets as nets
import nets.nasnet.pnasnet
import nets.inception_resnet_v2
from nets.inception_resnet_v2 import inception_resnet_v2_arg_scope
import random
import numpy as np


class A3CModel:

    def __init__(self, num_actions,
                 session = None,
                 train_deep = True,
                 rnn_size = 100,
                 is_for_train = True,
                 fixed_gate_probas = {}
                 ):
        
        self.num_actions = num_actions
        self.session = session
    
        self.init_op = None
        self.saver = None
        
        self.train_deep = train_deep
        self.rnn_size = rnn_size
        self.is_for_train = is_for_train
        self.fixed_gate_probas = fixed_gate_probas

        self.build()
        
    
    def init_from_checkpoint(self, checkpoint):
        
        inception_vars = tf.get_collection(
            tf.GraphKeys.GLOBAL_VARIABLES, 
            scope = 'InceptionResnetV2')

        saver = tf.train.Saver(var_list = inception_vars)
        saver.restore(self.session, checkpoint)
        
    
    def save(self, filename):
        if not self.saver:
            self.saver = tf.train.Saver()
        self.saver.save(self.session, filename)
        
    def restore(self, filename):
        if not self.saver:
            self.saver = tf.train.Saver()
        
        self.saver.restore(self.session, filename)

        
    def build(self):
        if self.session is None:
            self.session = tf.Session()
        
        self.build_inputs()
        self.build_cnn()
        self.build_lstm()
        self.build_a3c()
        self.add_loss()
        self.add_train_op()
    

    def build_inputs(self):
        with tf.variable_scope('inputs') as sc:
            self.move_rnn = tf.placeholder_with_default(True, (), "move_rnn")
            
            # Batch x 300 x 300
            self.img = tf.placeholder(tf.float32, (None, 300, 300, 3), "img")
            self.dropout = tf.placeholder(tf.float32, (), "dropout")
            
            # Learning Rate
            self.lr = tf.placeholder_with_default(0.1, (), 'lr')
            
            # l2 regularization
            self.l2 = tf.placeholder_with_default(0.01, (), 'l2')
            
            # Entropy Rate (use for regularization)
            self.er = tf.placeholder_with_default(0.01, (), 'er')
            
            # Batch, has indexes of chosed actions
            self.chosen_actions = tf.placeholder(tf.int32, (None), "chosen_actions")

            # Batch 
            self.is_action_applied = tf.placeholder(tf.float32, (None), "is_action_applied")

            # Actions that was done in the previous step
            self.prev_actions = tf.placeholder(tf.int32, (None), "prev_acitons")
            
            # Batch
            self.rewards = tf.placeholder(tf.float32, (None), 'rewards')

            # Batch x num_actions
            self.possible_actions = tf.placeholder(tf.float32, (None, self.num_actions - 1), 'possible_actions')


    def build_lstm(self):
        self.lstm_cell = tf.nn.rnn_cell.LSTMCell(self.rnn_size, state_is_tuple=True)
        self.lstm_init_state = self.lstm_cell.zero_state(1, dtype=tf.float32)
        
        actions_repr = tf.one_hot(self.prev_actions, self.num_actions - 1)
        actions_repr = tf.cast(actions_repr, dtype=tf.float32)
        img_repr = slim.fully_connected(self.net, 100)
        
        rnn_input = tf.concat([actions_repr, img_repr], -1)
        rnn_input = tf.expand_dims(rnn_input, 0)
        
        # Batch = 1, Time, Channels
        rnn_input = tf.reshape(rnn_input, (1, -1, 100 + self.num_actions - 1))
        
        self.rnn_output, self.state = tf.nn.dynamic_rnn(
            self.lstm_cell, rnn_input, initial_state = self.lstm_init_state)
        
        self.rnn_output = tf.reshape(self.rnn_output, (-1, self.rnn_size))
        
        output = tf.cond(self.move_rnn, 
                         lambda:self.rnn_output, 
                         lambda:self.lstm_init_state.h)
        
        output = tf.reshape(output, (-1, self.rnn_size))
        self.rnn_out = slim.flatten(slim.fully_connected(output, 100))
    
    
    def build_cnn(self):
        with slim.arg_scope(inception_resnet_v2_arg_scope()):
            self.net, endpoints = nets.inception_resnet_v2.inception_resnet_v2(
                   self.img, None, dropout_keep_prob = 1.0, is_training = self.is_for_train)
            # Batch x Channels
            self.net = slim.flatten(self.net)
                
            if not self.train_deep:
                self.net = tf.stop_gradient(self.net)

            self.text_pretrain = slim.fully_connected(self.net, 512, activation_fn=None)


    def build_a3c(self):
        l2_reg = slim.l2_regularizer(self.l2)
        he_init = tf.contrib.layers.variance_scaling_initializer(mode="FAN_AVG")
        xavier_init = tf.contrib.layers.xavier_initializer()
        zero_init = tf.constant_initializer(0)

        with tf.variable_scope('cnn') as sc:
            with slim.arg_scope([slim.conv2d, slim.fully_connected],
                                  weights_initializer = he_init,
                                  biases_initializer = zero_init,
                                  weights_regularizer = l2_reg
                                ):
                
                self.full_net = tf.concat([self.net, tf.stop_gradient(self.text_pretrain)], -1)
                self.fc1 = slim.fully_connected(self.full_net, 200)
                self.fc2 = slim.fully_connected(self.full_net, 200)
                self.fc3 = slim.fully_connected(self.full_net, 200)
               
                #self.policy_input = tf.concat([self.fc1, self.rnn_out], -1)
                self.policy_input = slim.dropout(self.fc1, self.dropout, scope='dropout')

                self.gate_input = tf.concat([self.fc2, self.rnn_out], -1)
                self.gate_input = slim.dropout(self.gate_input, self.dropout, scope='dropout')

                # Policy
                self.logits = slim.fully_connected(self.policy_input, self.num_actions - 1, activation_fn=None)
                self.pi = tf.nn.softmax(self.logits)
                
                # Policy with Prior knowledge of possible actions
                self.possible_proba = tf.clip_by_value(self.possible_actions, 1e-5, 1)
                self.prior_logits = self.logits + tf.log(self.possible_proba)
                self.prior_pi = tf.nn.softmax(self.prior_logits)

                # Apply/Do Nothing Gate
                # Batch x num_actions
                self.gate_logits = slim.fully_connected(self.gate_input, self.num_actions - 1, activation_fn=None)
                self.gate_proba = tf.nn.sigmoid(self.gate_logits)

                # Critic
                self.critic_input = tf.concat([self.fc3, self.rnn_out], -1)
                self.critic_input = slim.dropout(self.critic_input, self.dropout, scope='dropout')

                self.v = slim.fully_connected(self.policy_input, 1, activation_fn=None)
                self.v = slim.flatten(self.v)

                                
    def add_loss(self):
        # Advantage: reward - value
        # Reward couldn't be negative 
        # ToDo pass max Reward as input
        self.advantage = self.rewards - tf.clip_by_value(self.v, 0, 3)

        # Batch
        self.value_loss = tf.losses.mean_squared_error(self.rewards, self.v)
        
        # Policy Loss: Log(pi) * advantage
        # Batch
        filtered_logits = self.possible_actions * self.logits
        self.action_policy_loss = tf.nn.sparse_softmax_cross_entropy_with_logits(
             labels = self.chosen_actions,
             logits = filtered_logits)

        # Gate Policy Loss
        chosen_logits = tf.gather(self.gate_logits, self.chosen_actions, axis = -1)
        self.gate_policy_loss = tf.nn.sigmoid_cross_entropy_with_logits(
            labels = self.is_action_applied,
            logits = chosen_logits
        )

        self.gate_policy_loss = tf.reduce_sum( self.gate_policy_loss, axis=-1)

        self.policy_loss = (self.action_policy_loss + self.gate_policy_loss) * tf.stop_gradient(self.advantage)
        self.policy_loss = tf.reduce_mean(self.policy_loss)
        
        # Entropy: H(pi)  (regularization)
        # Take into account only possible actions
        pi_entropy = tf.nn.softmax_cross_entropy_with_logits_v2(
              labels = tf.nn.softmax(filtered_logits), 
              logits = filtered_logits)

        self.pi_entropy_loss = -self.er * tf.reduce_sum(pi_entropy, axis = -1)
        self.pi_entropy_loss = tf.reduce_mean(self.pi_entropy_loss)
        
        gate_entropy = - (tf.log(self.gate_proba)*self.gate_proba + tf.log(1 - self.gate_proba) + (1 - self.gate_proba))
        self.gate_entropy_loss = -self.er * gate_entropy
        self.gate_entropy_loss = tf.reduce_mean(self.gate_entropy_loss)

        # If the goal (reward 3 is hardcoded so far) is reached - then don't use entropy
        size = tf.shape(self.rewards)[0]
        self.dist = (3 - tf.gather(self.rewards, size - 1)) / 3.0
        self.entropy_loss = self.dist * (self.pi_entropy_loss + self.gate_entropy_loss)

        # Possible actions loss
        self.possible_loss = (1-self.possible_actions) * self.pi * self.pi
        self.possible_loss = tf.reduce_sum(self.possible_loss, -1)
        self.possible_loss = 10*tf.reduce_mean(self.possible_loss)

        # Final Loss
        self.loss = self.policy_loss + self.value_loss + self.entropy_loss + self.possible_loss
        

    def add_train_op(self):
        self.opt = tf.train.GradientDescentOptimizer(self.lr, use_locking=False)
        
        policy_train_op = self.opt.minimize(self.policy_loss + self.entropy_loss + self.possible_loss)
        value_train_op = self.opt.minimize(self.value_loss)
        
        self.train_op = tf.group(policy_train_op, value_train_op)
        
        
    def add_lstm_state(self, feed_dict, lstm_state = None):
        if lstm_state is None:
            feed_dict[self.lstm_init_state.h] = np.zeros((1, self.rnn_size), dtype=np.float32)
            feed_dict[self.lstm_init_state.c] = np.zeros((1, self.rnn_size), dtype=np.float32)
        else:
            feed_dict[self.lstm_init_state.h] = lstm_state.h
            feed_dict[self.lstm_init_state.c] = lstm_state.c


    def get_action(self, image, possible_actions, prev_action, lstm_state = None, return_next_state = False):
        """
        Returns Action Id
        """
        feed_dict = {
            self.img: [image],
            self.possible_actions: [possible_actions],
            self.prev_actions: [prev_action],
            self.dropout: 1.0
        }
        
        self.add_lstm_state(feed_dict, lstm_state)
        
        pi, gate_proba, new_lstm_state = self.session.run([self.prior_pi, self.gate_proba, self.state], feed_dict = feed_dict)
        pi = np.squeeze(pi)
        gate_proba = np.squeeze(gate_proba)
        print('got probabilities:', pi)

        action_id = np.random.choice(range(self.num_actions - 1), p = pi)

        action_proba = gate_proba[action_id]
        action_proba = self.fixed_gate_probas.get(action_id, action_proba)
        print('action_proba:', action_proba)
        
        to_apply = random.random() <= action_proba
        
        # move state
        if return_next_state:
            return (action_id, to_apply, new_lstm_state)
        else:
            return (action_id, to_apply)
    

    def estimate_score(self, image, prev_action, lstm_state = None):
        """
        Returns Score Estimation
        """
        feed_dict = {
            self.img: [image], 
            self.prev_actions: [prev_action],            
            self.dropout: 1.0
        }
        self.add_lstm_state(feed_dict, lstm_state)
        
        v = self.session.run(self.v, feed_dict = feed_dict)
        print('got score:', v)
        return v
                   
    
    def train_from_memory(self, memory, dropout = 1.0, lr = 0.01, er = 0.01, l2 = 0.01, lstm_state = None):
        
        # 1. Convert Memory to Input Batch
        batch = memory.to_input()
        batch_size = len(batch['img'])
        print('batch_size: ', batch_size)
        if batch_size <= 0:
            return (0, 0, 0)
        
        # 2. Create Feed Data
        prev_actions = [memory.prev_action] + batch['actions'][:-1]
        feed_dict = {
            self.img: batch['img'],
            self.chosen_actions: batch['actions'],
            self.is_action_applied: batch['is_applied'],

            self.prev_actions: prev_actions,
            self.rewards: batch['rewards'],
            self.possible_actions: batch['possible_actions'],

            self.dropout: dropout,
            self.lr: lr,
            self.er: er,
            self.l2: l2
        } 
        
        self.add_lstm_state(feed_dict, lstm_state)
        
        _, policy_loss, value_loss, entropy_loss = self.session.run(
            [self.train_op, self.policy_loss, self.value_loss, self.entropy_loss], feed_dict=feed_dict)
       
        return (policy_loss, value_loss, entropy_loss)

