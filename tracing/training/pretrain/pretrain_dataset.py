import tarfile
import urllib
import os.path


def extrace_archive(fname):
    if (fname.endswith("tar.gz")):
        tar = tarfile.open(fname, "r:gz")
        tar.extractall()
        tar.close()
    elif (fname.endswith("tar")):
        tar = tarfile.open(fname, "r:")
        tar.extractall()
        tar.close()

        
def download_dataset_imgs_if_need(url):
    if os.path.isdir('imgs'):
        return
    
    print('downloading imgs for dataset')
    archive_file = "controls_dataset_imgs.tar.gz"
    urllib.urlretrieve (dataset_imgs_url, 
                        archive_file)
    extrace_archive(archive_file)
    
    assert os.path.isdir('imgs'), "Something wrong in downloaded dataset"
    print('dataset downladed and unpacked')
    
