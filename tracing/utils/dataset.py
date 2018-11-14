import os, os.path
from abc import abstractmethod
import scipy.misc as misc
from PIL import Image
import numpy as np
import shutil

from tracing.utils.images import  ImageHelper


def slice(items, batch_size = 10):
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []

    if len(batch) > 0:
        yield batch

def read_small_image(url, width=300):
    file = url['img_file']
    assert os.path.isfile(file)
    small_file = create_small_picture(url)
    ih = ImageHelper()
    return ih.read_image(small_file, width)


def get_small_picture_file(file, width=300):
    assert file[-4:] == '.png', 'file format {} is not supported only png'.format(file)
    first_part = file[:-4]

    return first_part + '_width_{}.png'.format(width)


def create_small_picture(url, width=300):
    file = url['img_file']

    small_file = get_small_picture_file(file, width)
    if not os.path.isfile(small_file):
        # Resize image
        img = Image.open(file)
        scale = width / float(img.size[0])

        height = int((img.size[1] * scale))
        img = img.resize((width, height), Image.ANTIALIAS)
        img.save(small_file)

    return small_file

def is_empty(file):
    array = misc.imread(file)
    return np.all(array == array[0,0])


class IDataset:
    def __init__(self, items = None, path = None):

        self.path = path
        self.items = items

        if self.path:
            self.__read(path)

        assert self.items is not None, "items of file should be non empty"

    def __read(self, path):
        assert os.path.isdir(path) , "dataset path must be a directory"

        json = os.path.join(path, 'meta.json')
        csv = os.path.join(path, 'meta.csv')
        imgs_folder = os.path.join(path, 'imgs')

        assert os.path.isdir(imgs_folder)

        if os.path.exists(json):
            meta_file = json
        else:
            assert os.path.exists(csv), "meta.json or meta.csv must be in dataset"
            meta_file = csv

        items = []
        with open(meta_file, 'r') as f:
            for line, row in enumerate(f):
                row = row.strip()
                item = self.line2item(row)
                if item is None:
                    continue

                assert "img_file" in item, \
                    "img_file must be in item but wasn't found after reading {} line of file {}"\
                    .format(meta_file, line)

                # Correct Image file path in case it was stored with path
                fname = os.path.basename(item["img_file"])
                file = os.path.join(imgs_folder, fname)
                item['img_file'] = file

                items.append(item)

        self.items = items

    def save(self, path = None, format = None):
        if path is None:
            path = self.path

        assert path is not None, "file to save is not specified"
        assert os.path.isdir(path), "path must be a directory"

        json = os.path.join(path, 'meta.json')
        csv = os.path.join(path, 'meta.csv')
        imgs_folder = os.path.join(path, 'imgs')

        # 1. Detect format to save dataset
        if format:
            file = json if format == 'json' else csv
        elif os.path.exists(json):
            file = json
        elif os.path.exists(csv):
            file = csv
        else:
            raise AssertionError("Can't detect format of dataset to save. Set parameter format to csv or json.")

        tmp_file = file + '.tmp'
        with open(tmp_file, 'w') as f:
            for item in self.items:
                # 2. Copy image file
                file = item['img_file']
                file_name = os.path.basename(file)
                new_file = os.path.join(imgs_folder, file_name)
                if file != new_file:
                    shutil.copy(file, new_file)

                # 3. Save metadata
                line = self.item2line(item)
                f.write(line)
                f.write('\n')

        # 4. Move tmp meta
        shutil.move(tmp_file, file)

    @abstractmethod
    def line2item(self, line):
        raise NotImplementedError()

    @abstractmethod
    def item2line(self, item):
        raise NotImplementedError()

    def split_train_test(self, items, fraction = 0.8):
        split = int(round(len(items) * fraction))

        train = type(self)(items = items[:split])
        test = type(self)(items = items[split[:]])
        return (train, test)

    def slice(self, items, batch_size = 10):
        return slice(items, batch_size)

    def filter_empty_imgs(self):
        new_items = []
        for item in self.items:
            file = item['img_file']
            assert os.path.isfile(file), "file {} not found".format(file)

            if is_empty(file):
                continue

            new_items.append(item)

        self.items = new_items

    def create_small_pictures(self, width=300):
        for i, item in enumerate(self.items):
            if not os.path.isfile(item['img_file']):
                continue

            create_small_picture(item, width)





