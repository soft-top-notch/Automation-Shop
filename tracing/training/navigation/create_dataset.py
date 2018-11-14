import json
import os, os.path
import random
import uuid
import PIL
from PIL import Image
import sys

from tracing.utils.dataset import *


class CheckoutsDataset(IDataset):
    def __init__(self, items = None, file = None):
        super().__init__(items, file)

    def line2item(self, line):
        state, domain, url, file_name = line.strip().split('\t')

        return {
            'is_checkout': state == 'checkout_page',
            'img_file': file_name,
            'domain': domain,
            'state': state,
            'url': url
        }

    def item2line(self, item):
        state = item['state']
        domain = item['domain']
        url = item['url']
        file_name = item['img_file']
        
        return "{}\t{}\t{}\t{}".format(state, domain, url, file_name)

    @staticmethod
    def read(file):
        return CheckoutsDataset(file = file)


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
        no_checkout_pages = []
        for line_num, line in enumerate(f):
            sys.stdout.write('\r Processed lines: {}'.format(line_num))
            sys.stdout.flush()
            
            try:
                trace = json.loads(line)
            except:
                continue
            
            trace_state = trace['status']['state']
            print(trace_state)
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
                      destination = 'checkout_dataset/meta.csv',
                      destination_imgs ='checkout_dataset/imgs'):

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
                      destination = 'checkout_dataset/meta.csv',
                      destination_imgs ='checkout_dataset/imgs')
    print('dataset constructed')
    print('analyze it and correct labels with jupyter notebook')


