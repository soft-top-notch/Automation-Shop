import tarfile
import urllib
import urllib.request
import os.path
from pathlib import Path

class Downloader:

    classifier_model = "https://s3-us-west-2.amazonaws.com/g2-datascience/TRA/models/classification_model.tar.gz"
    inception_pretrained = "http://download.tensorflow.org/models/inception_resnet_v2_2016_08_30.tar.gz"

    checkout_dataset = "https://s3-us-west-2.amazonaws.com/g2-datascience/TRA/datasets/checkout_dataset.tar.gz"
    popup_dataset = "https://s3-us-west-2.amazonaws.com/g2-datascience/TRA/datasets/popups_dataset.tar.gz"
    popup_pretraining_dataset = "https://s3-us-west-2.amazonaws.com/g2-datascience/TRA/datasets/popups_pretrain.tar.gz"

    def __init__(self, path = None):
        if path is None:
            home = str(Path.home())
            path = os.path.join(home, '.tra_cache')

        self.path = path

    def extract_archive(self, fname, path):
        if fname.endswith("tar.gz"):
            tar = tarfile.open(fname, "r:gz")
            tar.extractall(path)
            tar.close()
        elif fname.endswith("tar"):
            tar = tarfile.open(fname, "r:")
            tar.extractall(path)
            tar.close()

    def download_resource(self, url, resource, clear_cache):
        path = os.path.join(self.path, resource)
        archive_file = os.path.join(self.path, resource + ".tar.gz")

        # 1. Clear cache if needs
        if clear_cache:
            if os.path.isdir(path):
                shutil.rmtree(path)
            if os.path.isfile(archive_file):
                os.remove(archive_file)

        # 2. if file exists - return it
        if os.path.exists(path):
            return path
        else:
            os.makedirs(path)

        # 3. Download file
        try:
            if not os.path.exists(archive_file):
                print('started downloading {} ...'.format(resource))
                urllib.request.urlretrieve(url, archive_file)
                print('finished downloading {}'.format(resource))
        except:
            if os.path.exists(archive_file):
                os.remove(archive_file)
            raise

        try:
            # 4. Extract archive
            self.extract_archive(archive_file, self.path)
            assert os.path.isdir(path), "incorrect archive"

            # 5. Return link
            return path

        except:
            shutil.rmtree(path)
            raise

    def download_classification_model(self, clear_cache = False):
        resource_path = self.download_resource(self.classifier_model, "classification_model", clear_cache)

        # Return checkpoint path in Tensorflow format
        return os.path.join(resource_path, "model")

    def download_inception_pretrained(self, clear_cache = False):
        resource_path = self.download_resource(self.inception_pretrained, "inception", clear_cache)
        file = "inception_resnet_v2_2016_08_30.ckpt"
        unpacked = os.path.join(self.path, file)
        dst = os.path.join(resource_path, file)
        os.rename(unpacked, dst)

        return dst

    def download_checkout_dataset(self, clear_cache = False):
        return self.download_resource(self.checkout_dataset, "checkout_dataset", clear_cache)

    def download_popup_dataset(self, clear_cache = False):
        return self.download_resource(self.popup_dataset, "popups_dataset", clear_cache)

    def popup_pretraining_dataset(self, clear_cache = False):
        return self.download_resource(self.popup_pretraining_dataset, "popup_pretraining_dataset", clear_cache)
