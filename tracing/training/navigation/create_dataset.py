import json
import os, os.path
import random
import uuid
import PIL
from PIL import Image
import sys



def load_dataset(dataset_file = 'checkout_dataset.csv', imgs_path = None):
    result = []
    with open(dataset_file, 'r') as f:
        for line in f:
            state, domain, url, file_name = line.strip().split('\t')
            
            if imgs_path:
                file_name = os.path.join(imgs_path, file_name)
            
            item = {
                'is_checkout': state == 'checkout_page',
                'img_file': file_name
            }
            result.append(item)
    
    return result


def is_img(file):
    if not os.path.exists(file):
        return False
    
    try:
        im=Image.open(file)
        return True
    except IOError:
        return False

    
def sample(file, 
                sample_from_path_to_checkout = 5, 
                sample_from_non_checkout = 5.0):
    
    print('started sampling dataset')
    sample_from_path_to_checkout = int(round(sample_from_path_to_checkout))
    
    # pairs trace_num, step
    no_checkout_pages = []
    
    # pairs trace_num, step
    result = []
    checkout_pages = 0
    
    with open(file, 'r') as f:
        for line_num, line in enumerate(f):
            sys.stdout.write('\r Processed lines: {}'.format(line_num))
            sys.stdout.flush()
            
            try:
                trace = json.loads(line)
            except:
                continue
            
            trace_state = trace['status']['state']
            if trace_state == 'checkout_page' or trace_state == 'purchased':
                checkout_pages += 1
                
                reached_checkout = False
                path = []
                for i, step in enumerate(trace['steps']):
                    if not is_img(step['screen_path']):
                        continue
                    
                    # Add All checkout pages to training dataset
                    if step['state'] == 'checkout_page':
                        result.append((line_num, i))
                        reached_checkout = True
                    else:
                        # We don't want to collect pay pages as they may confuse
                        if reached_checkout: 
                            break
                            
                        path.append((line_num, i))
                
                
                if len(path) <= sample_from_path_to_checkout:
                    result.extend(path)
                else:
                    sample = random.sample(path, sample_from_path_to_checkout)
                    result.extend(sample)
                    
                    
            else:
                for i, step in enumerate(trace['steps']):
                    if not is_img(step['screen_path']):
                        continue

                    no_checkout_pages.append((line_num, i))
                
    no_checkout_size = int(round(checkout_pages * sample_from_non_checkout))
    to_add = random.sample(no_checkout_pages, no_checkout_size)
    result.extend(to_add)
    
    result.sort()
    
    return result


def create_small_picture(img_file, dst_folder, width=300):
    file = str(uuid.uuid4()).replace('-', '') + '.png'
    dst_file = os.path.join(dst_folder, file)
    
    # Resize image
    img = Image.open(img_file)
    scale = width / float(img.size[0])

    height = int((img.size[1] * scale))
    img = img.resize((width, height), Image.ANTIALIAS)
    img.save(dst_file)
    
    return dst_file
        

def construct_dataset(file, 
                      sample_from_path_to_checkout = 5.0, 
                      sample_from_non_checkout = 5.0, 
                      destination = 'checkout_dataset.csv', 
                      destination_imgs ='checkout_dataset_imgs'):

    if not os.path.exists(destination_imgs):
        os.makedirs(destination_imgs)
    else:
        print('cleaning old files')
        old_files = [ f for f in os.listdir(destination_imgs) if f.endswith(".png") ]
        for old_file in old_files:
            os.remove(os.path.join(destination_imgs, old_file))
    
    to_store = sample(file, sample_from_path_to_checkout, sample_from_non_checkout)
    idx = 0
    
    print('\n\nSaving dataset')
    with open(destination, 'w') as f_out:
        with open(file, 'r') as f:
            for line_num, line in enumerate(f):
                sys.stdout.write('\r finished {:2.2f} %'.format(idx * 100 / len(to_store)))
                sys.stdout.flush()
                
                if line_num < to_store[idx][0]:
                    continue

                assert line_num == to_store[idx][0]

                trace = json.loads(line)
                for i, step in enumerate(trace['steps']):
                    if i < to_store[idx][1]:
                        continue

                    assert i == to_store[idx][1]
                    
                    try:
                        file = create_small_picture(step['screen_path'], destination_imgs)
                    except:
                        print('is file exists', os.path.exists(step['screen_path']))
                        raise
                    f_out.write('{}\t{}\t{}\t{}\n'
                                .format(step['state'], trace['domain'], step['url'], file))
                    
                    idx += 1
                    if idx >= len(to_store):
                        return
                    
                    if to_store[idx][0] > line_num:
                        break


if __name__ == '__main__':
    print('started creatign checkouts dataset')
    construct_dataset('log/results.jsonl', 
                      sample_from_path_to_checkout = 5.0, 
                      sample_from_non_checkout = 5.0, 
                      destination = 'checkout_dataset.csv', 
                      destination_imgs ='checkout_dataset_imgs')
    print('dataset constructed')
    print('analyze it and correct labels with jupyter notebook')


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
        with tf.variable_scope('page_classification') as sc:
            self.dropout = tf.placeholder(tf.float32, (), "dropout")
            self.lr = tf.placeholder(tf.float32, (), "lr")
            self.l2 = tf.placeholder(tf.float32, (), "l2")

            self.img = tf.placeholder(tf.float32, (None, None, 300, 3), "img")
            self.popup_labels = tf.placeholder(tf.float32, (None, 2), "popup_labels")
            self.checkout_labels = tf.placeholder(tf.float32, (None, 2), "checkout_labels")
            
            # Bit mask detecting if it's a popups task
            self.is_popup_task = tf.placeholder(tf.bool, [None], "is_popup")
            self.is_checkout_task = tf.placeholder(tf.bool, [None], "is_checkout")
            

        with slim.arg_scope(inception_resnet_v2_arg_scope()):
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
    
    
    def train(self, imgs, epochs = 10, lr = 0.001, dropout = 0.8, l2 = 0.001):
        
        print('dataset size:', len(imgs))
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
                
                _, loss, popup_loss, checkout_loss = self.session.run(
                    [self.train_op, self.loss, self.popup_loss, self.checkout_loss], 
                                           feed_dict = feed)
                
                print('loss: {}, popup_loss: {}, checkout_loss: {}'.format(loss, popup_loss, checkout_loss))
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
test_urls = train_checkouts + test_checkouts

random.shuffle(train_urls)
random.shuffle(test_urls)


tf.reset_default_graph()
session = tf.Session()

classifier = PageClassifier(session)
session.run(tf.global_variables_initializer())

saver = tf.train.Saver()
#classifier.restore_inception('./inception_resnet_v2_2016_08_30.ckpt')

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

train_urls = train_urls
test_urls = test_urls


for epoch in range(start_epoch, 100):
    print('epoch ', epoch)
    classifier.train(train_urls, epochs=1, lr = 0.0001, dropout = 1.0)# 0.65)
    train_f1 = classifier.measure(train_urls)
    print('train f1:', train_f1)
    
    test_f1 = classifier.measure(test_urls)
    print('test f1:', test_f1)
    
    if epoch % 10 == 9:
        saver.save(session, 'classification_model/{}'.format(epoch))



