import tempfile
import tracing.selenium_utils.common as common
import tracing.selenium_utils.controls as selenium_controls
from PIL import Image
from scipy import misc
import os
import numpy as np
import traceback
import time
    

class Environment:
    
    def __init__(self, rewards, user, width = 612, headless = True):
        self.rewards = rewards
        self.user = user
        self.width = width
        self.headless = headless
        self.step = 0
        self.driver = None

    def __enter__(self):
        pass

    def is_final(self):        
        return self.rewards.is_final()
    
    def start(self, url):
        if self.driver is not None:
            self.driver.quit()
        
        self.driver = common.create_chrome_driver(headless = self.headless)

        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'http://' + url
        
        self.driver.get(url)
        self.rewards.start()
        self.step = 0
        
        time.sleep(5)
    
    def __exit__(self, type, value, traceback):
        print("exit is called")
        if self.driver is not None:
            self.driver.quit()
            self.driver = None

    # Returns 3D Numpy array of image representation
    # Channels x Width X Height
    def get_screenshot_as_array(self):
        assert self.driver is not None
        
        # 1. Create temp file
        f, tmp = tempfile.mkstemp(suffix='.png')
        os.close(f)

        # 2. Take a screenshot
        scale = common.get_scale(self.driver)    
        common.get_full_page_screenshot(self.driver, tmp, scale)    

        # 3. Resize image
        img = Image.open(tmp)
        width_scale = (self.width / float(img.size[0]))
        height = int((float(img.size[1]) * float(width_scale)))
        img = img.resize((self.width, height), Image.ANTIALIAS)
        img.save(tmp)

        # 4. Read as a numpy array
        image = misc.imread(tmp)
        os.remove(tmp)

        [h, w, _] = image.shape
        if h < w:
            to_add = np.ndarray([w-h, w, 3], dtype=float)
            to_add.fill(0)
            image = np.append(image, to_add, axis=0)
        
        return image

    def get_control_as_input(self, ctrl):
        source_image = self.get_screenshot_as_array()
            
        image = (source_image - 128.0) / 128.0
        common.scroll_to_top(self.driver)
        
        [h, w, _] = image.shape
        mask = np.ndarray([h, w, 1], dtype=float)
        mask.fill(0)
        top = ctrl.location['y']
        left = ctrl.location['x']
        bottom = top + ctrl.size['height']
        right = left + ctrl.size['width']

        mask[top:bottom, left:right, 0] = 1
        array = np.append(image, mask, axis=-1)
        
        return array

    
    # Returns input images for different controls
    def get_controls(self):
        
        source_image = self.get_screenshot_as_array()
            
        image = (source_image - 128.0) / 128.0
        common.scroll_to_top(self.driver)
        
        controls = selenium_controls.extract_controls(self.driver)

        # Sort by Top then by Left of control location
        controls.sort(key = lambda ctrl: (ctrl.location['y'], ctrl.location['x']))
        
        return controls
    
    def apply_action(self, control, action):
        success = False
        try:
            self.rewards.before_action(self.driver, action)
            self.step += 1
            success = action.apply(control, self.driver, self.user)
        except:
            success = False
            traceback.print_exc()
        finally:
            self.rewards.after_action(self.driver, action)
            
        return self.rewards.calc_reward(success)
    
    def calc_final_reward(self):
        return self.rewards.calc_final_reward()
