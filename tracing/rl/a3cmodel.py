import tensorflow as tf
import tensorflow.contrib.slim as slim
import numpy as np

class A3CModel:
    global_scope = "global_model_scope"
    local_scope = "local_model_scope"
    
    def __init__(self, num_actions, global_model = None, session = None, name = None):
        self.num_actions = num_actions
        self.global_model = global_model
        self.session = session
        self.name = name or ''
        
        self.build()
        
    @property
    def is_global(self):
        return self.global_model is None
        
    def build(self):
        if self.session is None:
            self.session = tf.Session()
        
        if self.is_global:
            with tf.variable_scope(A3CModel.global_scope):
                self.build_graph()
                self.add_loss()
                self.params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=A3CModel.global_scope)
                self.add_train_op()
        else:
            with tf.variable_scope(A3CModel.local_scope + self.name):
                self.build_graph()
                self.add_loss()
                self.params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=A3CModel.local_scope + self.name)
                self.add_update_ops()

    
    def build_graph(self):
        with tf.variable_scope('inputs') as sc:
            # Batch x h x 612
            self.img = tf.placeholder(tf.float32, (None, None, None, 4), "img")
            self.dropout = tf.placeholder(tf.float32, (), "dropout")
            
            # Learning Rate
            self.lr = tf.placeholder_with_default(0.1, (), 'lr')
            
            # Entropy Rate (use for regularization)
            self.er = tf.placeholder_with_default(0.01, (), 'er')
            
            # Batch, Number of Action
            self.performed_actions = tf.placeholder(tf.int32, (None), "performed_actions")
            
            # Batch
            self.rewards = tf.placeholder(tf.float32, (None), 'rewards')

        with tf.variable_scope('cnn') as sc:

            end_points_collection = sc.original_name_scope + '_ep'

            with slim.arg_scope([slim.conv2d, slim.fully_connected, slim.max_pool2d],
                                outputs_collections=[end_points_collection]):

                # h/2, 306
                net = slim.conv2d(self.img, 64, [5, 5], 2, padding='SAME',
                                scope='conv1')

                # h/4, 153
                net = slim.conv2d(net, 64, [5, 5], 2, padding='SAME',
                                scope='conv2')

                # h/8, 76
                net = slim.max_pool2d(net, [3, 3], 2, scope='pool1')
                net = slim.conv2d(net, 64, [5, 5], scope='conv3')

                # h/16, 38
                net = slim.max_pool2d(net, [3, 3], 2, scope='pool2')
                net = slim.conv2d(net, 64, [3, 3], scope='conv4')
                net = slim.conv2d(net, 64, [3, 3], scope='conv5')
                net = slim.conv2d(net, 64, [3, 3], scope='conv6')

                # h/32, 18
                net = slim.max_pool2d(net, [3, 3], 2, scope='pool5')

            # Use conv2d instead of fully_connected layers.
            with slim.arg_scope([slim.conv2d],
                                  weights_initializer=tf.truncated_normal_initializer(0.005),
                                  biases_initializer=tf.constant_initializer(0.1)):

                # h/32 - 3, 1
                net = slim.avg_pool2d(net, [18, 18], padding='VALID',
                                  scope='fc')
                net = slim.dropout(net, self.dropout, scope='dropout')

                # h/32 - 3, 1
                net = slim.conv2d(net, 128, [1, 1], scope='fc2')

                # Convert end_points_collection into a end_point dict.
                end_points = slim.utils.convert_collection_to_dict(end_points_collection)

                # 128, Global Max Pooling
                net = tf.reduce_max(net, [1, 2], keepdims=False, name='global_pool')
                end_points['global_pool'] = net

                # Policy
                self.logits = slim.fully_connected(net, self.num_actions)

                self.pi = tf.nn.softmax(self.logits)
                self.v = slim.fully_connected(net, 1)

        self.end_points = end_points
        return net, end_points

    
    def init_weights(self):
        self.session.run(tf.global_variables_initializer())

    def add_loss(self):
        # Advantage
        advantage = self.rewards - self.v
        value_loss = tf.nn.l2_loss(advantage)
        
        # Policy Loss: Log(pi) * advantage
        policy_loss = tf.nn.sparse_softmax_cross_entropy_with_logits(
            labels=self.performed_actions, logits=self.logits)
        policy_loss *= tf.stop_gradient(advantage)
        
        # Entropy: H(pi)
        entropy = -tf.reduce_sum(self.pi * tf.log(self.pi), axis=1, keepdims=True)  # encourage exploration
        
        # Summ Loss
        self.loss = tf.reduce_mean(0.5 * value_loss + policy_loss - self.er * entropy)
       
        
    def add_train_op(self):
        self.opt = tf.train.AdamOptimizer()


    def add_update_ops(self):
        assert not self.is_global, "Can't add pull and push operations to global model"
        assert self.global_model is not None, "Global model must bet set"
        assert self.global_model.opt is not None, "Global model must have optimizer .opt"
               
        with tf.name_scope('update'):
            # Gradients Computation
            self.grads = [g for g in tf.gradients(self.loss, self.params) if g is not None]
            
            # Pull variables from global model
            self.pull_global_op = [local_var.assign(global_var) for local_var, global_var in 
                            zip(self.params, self.global_model.params)]
            
            # Add gradients to global model variables
            opt = self.global_model.opt
            self.update_global_op = self.global_model.opt.apply_gradients(
                zip(self.grads, self.global_model.params))
            
    
    def update_global(self, feed_dict):
        self.session.run([self.update_global_op], feed_dict)  
        
    def pull_global(self):
        self.session.run([self.pull_global_op])

    def get_action(self, image):
        """
        Returns Action Id
        """
        print('image shape:', image.shape)
        pi = self.session.run(self.pi, feed_dict = {self.img: [image], self.dropout: 1.0})
        print('got probabilities:', pi)
        return np.random.choice(range(self.num_actions), p = pi[0])
    
    def train_from_memory(self, memory, dropout = 1.0, lr = 0.01, er = 0.01):
        assert not self.is_global, "Can't train Global Model"
        
        # 1. Convert Memory to Input Batch
        batch = memory.to_input()
        batch_size = len(batch['img'])
        print('batch_size: ', batch_size)
        if batch_size <= 0:
            return
        
        # 2. Create Feed Data
        feed_data = {
            self.img: batch['img'],
            self.performed_actions: batch['actions'],
            self.rewards: batch['rewards'],

            self.dropout: dropout,
            self.global_model.lr: lr,
            self.er: er
        }    
        
        # 3. Compute gradients and update global Model
        self.update_global(feed_data)
        
        # 4. Copy Values from Global Model
        self.pull_global()

