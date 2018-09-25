import tensorflow as tf
import tensorflow.contrib.slim as slim
import tensorflow.contrib.slim.nets as nets
import nets.nasnet.pnasnet
import nets.inception_resnet_v2
from nets.inception_resnet_v2 import inception_resnet_v2_arg_scope


import numpy as np

class A3CModel:
    global_scope = "global_model_scope"
    local_scope = "local_model_scope"
    
    def __init__(self, num_actions, 
                 global_model = None, 
                 session = None,
                 train_deep = True
                 ):
        
        self.num_actions = num_actions
        self.session = session
    
        self.init_op = None
        self.saver = None
        
        self.train_deep = train_deep
        
        self.build()
        
    
    def init_from_checkpoint(self, checkpoint):
        self.init()
        
        inception_vars = tf.get_collection(
            tf.GraphKeys.GLOBAL_VARIABLES, 
            scope = 'InceptionResnetV2')

        saver = tf.train.Saver(var_list = inception_vars)
        saver.restore(self.session, checkpoint)
        
    
    def init(self):
        if self.init_op is None:
            self.init_op = tf.variables_initializer(self.all_params, name='init')

        self.session.run(self.init_op)

    def save(self, filename):
        assert self.is_global, "only global model makes sense to save and load"
        
        if not self.saver:
            self.saver = tf.train.Saver()
        self.saver.save(self.session, filename)
        
    def restore(self, filename):
        assert self.is_global, "only global model makes sense to save and load"
        
        if not self.saver:
            self.saver = tf.train.Saver()
        
        self.saver.restore(self.session, filename)

        
    def build(self):
        if self.session is None:
            self.session = tf.Session()
        
        self.build_graph()
        self.add_loss()
        self.add_train_op()
        self.params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=A3CModel.global_scope)
        self.all_params = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=A3CModel.global_scope)
            
    
    def build_graph(self):
        with tf.variable_scope('inputs') as sc:
            # Batch x h x 612
            self.img = tf.placeholder(tf.float32, (None, 300, 300, 3), "img")
            self.dropout = tf.placeholder(tf.float32, (), "dropout")
            
            # Learning Rate
            self.lr = tf.placeholder_with_default(0.1, (), 'lr')
            
            # l2 regularization
            self.l2 = tf.placeholder_with_default(0.01, (), 'l2')
            
            # Entropy Rate (use for regularization)
            self.er = tf.placeholder_with_default(0.01, (), 'er')
            
            # Batch, Number of Action
            self.performed_actions = tf.placeholder(tf.int32, (None), "performed_actions")
            
            # Batch
            self.rewards = tf.placeholder(tf.float32, (None), 'rewards')

            # Batch x num_actions
            self.possible_actions = tf.placeholder(tf.float32, (None, self.num_actions), 'possible_actions')

        l2_reg = slim.l2_regularizer(self.l2)
        he_init = tf.contrib.layers.variance_scaling_initializer(mode="FAN_AVG")
        xavier_init = tf.contrib.layers.xavier_initializer()
        zero_init = tf.constant_initializer(0)
        
        with slim.arg_scope(inception_resnet_v2_arg_scope(batch_norm_updates_collections=[])):
            self.net, endpoints = nets.inception_resnet_v2.inception_resnet_v2(self.img, None, dropout_keep_prob = 1.0, is_training = False)


        with tf.variable_scope('cnn') as sc:
            with slim.arg_scope([slim.conv2d, slim.fully_connected],
                                  weights_initializer = he_init,
                                  biases_initializer = zero_init,
                                  weights_regularizer = l2_reg
                                ):
                
                # Batch x Channels
                self.net = slim.flatten(self.net)
                
                if not self.train_deep:
                    self.net = tf.stop_gradient(self.net)

                self.fc2 = slim.fully_connected(self.net, 100)
                self.flat = slim.dropout(self.fc2, self.dropout, scope='dropout')

                # Policy
                self.logits = slim.fully_connected(self.flat, self.num_actions, activation_fn=None)

                self.possible_proba = tf.clip_by_value(self.possible_actions, 1e-5, 1)
                self.possible_logits = self.logits + tf.log(self.possible_proba)

                self.pi = tf.nn.softmax(self.possible_logits)

                self.v = slim.fully_connected(tf.stop_gradient(self.flat), 1, activation_fn=None)
                self.v = slim.flatten(self.v)

                                
    def add_loss(self):
        # Advantage: reward - value
        # Reward couldn't be negative 
        # ToDo pass max Reward as input
        self.advantage = self.rewards - tf.clip_by_value(self.v, 0, 3)

        # Batch
        self.value_loss = tf.losses.mean_squared_error(self.rewards, self.v)
        
        # Policy Loss: Log(pi) * advantage
        # Batch x actions
        self.policy_loss = tf.nn.sparse_softmax_cross_entropy_with_logits(
             labels = self.performed_actions, 
             logits = self.possible_logits)

        # Batch
        self.policy_loss *= tf.stop_gradient(self.advantage)
        self.policy_loss = tf.reduce_mean(self.policy_loss)
        
        # Entropy: H(pi)  (regularization)
        entropy = tf.nn.softmax_cross_entropy_with_logits_v2(labels = tf.nn.softmax(self.logits), logits = self.logits)
        # Batch
        self.entropy_loss = -self.er * tf.reduce_sum(entropy, axis = -1)
        size = tf.shape(self.rewards)[0]
        self.dist = (3 - tf.gather(self.rewards, size - 1)) / 3.0
        self.entropy_loss = self.dist * tf.reduce_mean(self.entropy_loss)

        # Final Loss
        self.loss = self.policy_loss + self.value_loss + self.entropy_loss
           

    def add_train_op(self):
        self.opt = tf.train.GradientDescentOptimizer(self.lr, use_locking=False)
        
        policy_train_op = self.opt.minimize(self.policy_loss + self.entropy_loss)
        value_train_op = self.opt.minimize(self.value_loss)
        
        self.train_op = tf.group(policy_train_op, value_train_op)
        

    def add_update_ops(self):
        assert not self.is_global, "Can't add pull and push operations to global model"
        assert self.global_model is not None, "Global model must bet set"
        assert self.global_model.opt is not None, "Global model must have optimizer .opt"
               
        with tf.name_scope('update'):
            # Pull variables from global model
            self.pull_global_op = [local_var.assign(global_var) for local_var, global_var in 
                            zip(self.params, self.global_model.params)]
            
            # Add gradients to global model variables
            opt = self.global_model.opt
        
            # Gradients Computation
            self.grads = [g for g in tf.gradients(self.loss, self.params)]
            self.grads = [(g, v) for (g, v) in zip(self.grads, self.global_model.params) if g is not None]
            self.grads = [(tf.clip_by_value(g, -200., 200.), v) for g, v in self.grads]
            
            self.update_global_op = opt.apply_gradients(self.grads)
            
    
    def get_action(self, image, possible_actions):
        """
        Returns Action Id
        """
        feed_dict = {
            self.img: [image],
            self.possible_actions: [possible_actions], 
            self.dropout: 1.0
        }
        pi = self.session.run(self.pi, feed_dict = feed_dict)
        pi = np.squeeze(pi)
        print('got probabilities:', pi)
        return np.random.choice(range(self.num_actions), p = pi)
    

    def estimate_score(self, image):
        """
        Returns Score Estimation
        """
        v = self.session.run(self.v, feed_dict = {self.img: [image], self.dropout: 1.0})
        print('got score:', v)
        return v


    def train_from_memory_cv(self, memory, dropout = 1.0, lr = 0.01, er = 0.01):
        assert not self.is_global, "Can't train Global Model"
        
        batch = memory.to_input()
        batch_size = len(batch['img'])
        if batch_size <= 0:
            return 0

        feed_data = {
            self.img: batch['img'],
            self.possible_actions: batch['possible_actions'],

            self.dropout: dropout,
            self.lr: lr
        }
        
        loss = self.update_global_cv(feed_data)
        self.pull_global()
        
        return loss
       
    
    def train_from_memory(self, memory, dropout = 1.0, lr = 0.01, er = 0.01, l2 = 0.01):
        
        # 1. Convert Memory to Input Batch
        batch = memory.to_input()
        batch_size = len(batch['img'])
        print('batch_size: ', batch_size)
        if batch_size <= 0:
            return (0, 0, 0)
        
        # 2. Create Feed Data
        feed_dict = {
            self.img: batch['img'],
            self.performed_actions: batch['actions'],
            self.rewards: batch['rewards'],
            self.possible_actions: batch['possible_actions'],

            self.dropout: dropout,
            self.lr: lr,
            self.er: er,
            self.l2: l2
        } 
        
        _, policy_loss, value_loss, entropy_loss = self.session.run(
            [self.train_op, self.policy_loss, self.value_loss, self.entropy_loss], feed_dict=feed_dict)
       
        return (policy_loss, value_loss, entropy_loss)

