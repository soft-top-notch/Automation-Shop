import tempfile
import uuid
import os
import os.path
import json
from tracing.heuristic.shop_tracer import ITraceListener
import tracing.selenium_utils.common as common
from tracing.utils.images import *
from tracing.rl.actions import Actions
import traceback


class ActionsFileRecorder(ITraceListener):

    def __init__(self, dataset):
        self.create_tmp_files()
        self.dataset = dataset

        self.ih = ImageHelper()
        assert not os.path.exists(dataset) or os.path.isdir(dataset), \
            "dataset path {} should be a folder".format(dataset)

        self.dataset_imgs = os.path.join(self.dataset, 'imgs')
        os.makedirs(self.dataset_imgs, exist_ok=True)

        self.dataset_meta = os.path.join(self.dataset, 'meta.jsonl')
        if not os.path.exists(self.dataset_meta):
            f = open(self.dataset_meta, 'w')
            f.close()

    def on_tracing_started(self, domain):
        self.domain = domain

    def on_tracing_finished(self, status):
        self.flush()

    def create_tmp_files(self):
        # Create Tmp file for trace
        fd, self.results_file = tempfile.mkstemp('.csv')
        os.close(fd)
        self.imgs_folder = tempfile.mkdtemp()

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.remove(self.results_file)
        os.remove(self.imgs_folder)

    def get_new_img_file(self):
        fname = str(uuid.uuid4()).replace('-', '') + '.png'
        return os.path.join(self.imgs_folder, fname)

    def before_action(self, environment, control = None, state = None):
        self.control_file = None
        self.control_label = None
        self.possible_actions = None

        # 1. Save control image
        if control is not None:
            try:
                inp = environment.get_control_as_input(control)
                self.control_file = self.get_new_img_file()

                pa = []
                for action in Actions.navigation:
                    bit = 1 if action.is_applicable(control) else 0
                    pa.append(bit)

                self.possible_actions = pa
                self.ih.input2img(inp, self.control_file)
                self.control_label = control.label
            except:
                traceback.print_exc()

        # 2. Save state image
        self.state_file = self.get_new_img_file()
        common.get_screenshot(environment.driver, self.state_file)

        # 3. Save current url
        self.url = common.get_url(environment.driver)
        self.state = state


    def after_action(self, action, is_success, new_state = None):
        status = {
            'domain': self.domain,
            'url': self.url,
            'control_img': os.path.basename(self.control_file) if self.control_file else None,
            'state_img': os.path.basename(self.state_file),
            'action': action.__class__.__name__,
            'is_success': is_success,
            'possible_actions': self.possible_actions,
            'state': self.state,
            'new_state': new_state,
            'control_label': self.control_label
        }

        line = json.dumps(status) + '\n'
        with open (self.results_file, 'a') as f:
            f.write(line)
            f.flush()

    def move_file(self, fname, src_folder, dst_folder):
        src = os.path.join(src_folder, fname)
        dst = os.path.join(dst_folder, fname)

        os.rename(src, dst)

    def flush(self):
        # Move recorded data from temp folder to dataset
        with open(self.dataset_meta, 'a') as dst, open(self.results_file, 'r') as src:
            for line in src:
                info = json.loads(line.strip())
                if info.get('control_img') is not None:
                    self.move_file(info['control_img'], self.imgs_folder, self.dataset_imgs)
                self.move_file(info['state_img'], self.imgs_folder, self.dataset_imgs)

                dst.write(line.strip() + '\n')
                dst.flush()

        # clear temp file
        open(self.results_file, 'w').close()