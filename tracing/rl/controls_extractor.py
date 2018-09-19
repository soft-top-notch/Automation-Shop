from tracing.rl.environment import Environment
from tracing.rl.actions import Actions
import tracing.selenium_utils.common as common
import csv, re
from PIL import Image
import numpy as np
import uuid
import os
import json
import random
import threading
from queue import Queue


class ControlsExtractor:

    def __init__(self, img_folder, dataset_file, queue):
        self.img_folder = img_folder
        self.dataset_file = dataset_file
        self.queue = queue

    
    @staticmethod
    def get_possible_actions(ctrl, include_none = True):
        num_actions = len(Actions.actions)
        if not include_none:
            num_actions -= 1
        
        possible_actions = []
        for a_id, action in enumerate(Actions.actions[:num_actions]):
            is_applicable = 1 if action.is_applicable(ctrl) else 0
            possible_actions.append(is_applicable)
        
        return possible_actions        
    
    
    def start(self):
        while True:
            url = self.queue.get()
            self.extract(url)
       
    def extract(self, url):
        env = Environment()
        with env:
            if not env.start(url):
                return 
            
            while env.has_next_control():
                ctrl = env.get_next_control()
                try:
                    inp = env.get_control_as_input(ctrl)
                except:
                    continue
                    
                rgb = (inp * 128 + 128).astype(np.uint8)
                img = Image.fromarray(rgb, 'RGB')
                
                img_file = str(uuid.uuid4()) + '.png'
                img_file = os.path.join(self.img_folder, img_file)
                img.save(img_file)
                
                pa = ControlsExtractor.get_possible_actions(ctrl, False)
                
                info = {
                    'url': url,
                    'type': ctrl.type,
                    'label': ctrl.label,
                    'possible_actions': pa,
                    'code': ctrl.code,
                    'img_file': img_file,
                    'height': ctrl.ext_size['height'],
                    'width': ctrl.ext_size['width']
                }
                
                with open(self.dataset_file, 'a') as f:
                    f.write(json.dumps(info))
                    f.write('\n')


smoke_urls = []

pattern = '(smok)|(cig)|(vape)|(tobac)'
with open('../../resources/pvio_vio_us_ca_uk_sample1.csv') as f:
    rows = csv.reader(f)
    for row in rows:
        url = row[0]
        if re.match(pattern, url):
            smoke_urls.append(url)

print('Found {} url'.format(len(smoke_urls)))

queue = Queue()
for url in smoke_urls:
    queue.put(url)


num_threads = 4

imgs_folder = 'imgs'
dataset = 'dataset.jsonl'

# Create or clear results file
open(dataset, 'w').close()

# create image folder if not exists
if not os.path.exists(imgs_folder):
    os.makedirs(imgs_folder)

# Delete all .png files in directory
old_files = [ f for f in os.listdir(imgs_folder) if f.endswith(".png") ]
for file in old_files:
    os.remove(os.path.join(imgs_folder, file))


for _ in range(num_threads):
    extractor = ControlsExtractor(imgs_folder, dataset, queue)
    t = threading.Thread(target=extractor.start)
    t.daemon = True
    t.start()

queue.join()


