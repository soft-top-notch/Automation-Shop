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
    
    def __init__(self, rewards = None, user = None, width = 612, 
            headless = True,
            crop_h = 224,
            crop_w = 224
            ):
        self.rewards = rewards
        self.user = user
        self.width = width
        self.headless = headless
        self.step = 0
        self.driver = None
        self.crop_h = crop_h
        self.crop_w = crop_w

    def __enter__(self):
        pass

    def is_final(self):
        assert self.rewards is not None

        return self.rewards.is_final()
    

    def start(self, url):
        self.try_quit_driver()
        
        try:
            self.driver = common.create_chrome_driver(headless = self.headless)

            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'http://' + url
        
            self.driver.get(url)
            if self.rewards:
                self.rewards.start()

            self.step = 0
            self.controls = None
            self.c_idx = 0
        
        except:
            traceback.print_exc()
            return False
        
        time.sleep(5)
        return True

    
    def __exit__(self, type, value, traceback):
        print("exit is called")
        self.try_quit_driver()


    def try_quit_driver(self):
        try:
            if self.driver is not None:
                self.driver.quit()
        except:
            traceback.print_exc()

        self.driver = None


    def has_next_control(self):
        if self.controls is None:
            self.controls = self.get_controls()
        
        while self.c_idx < len(self.controls):
            ctrl = self.controls[self.c_idx]
            if not common.is_stale(ctrl.elem):
                return True
            
            self.c_idx += 1

        return False
    

    def get_next_control(self, move = True):
        assert self.has_next_control()
	
        ctrl = self.controls[self.c_idx]
        if move:
            self.c_idx += 1
        
        return ctrl


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
        self.width_scale = self.width / float(img.size[0])

        height = int((img.size[1] * self.width_scale))
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

    def crop_image(self, image, center_x, center_y):
        (h, w, c) = image.shape

        top = max(center_y - (self.crop_h - 1)//2, 0)
        left = max(center_x - (self.crop_w - 1) // 2, 0)
        bottom = min(center_y + (self.crop_h + 2) // 2, h)
        right = min(center_x + (self.crop_w + 2) // 2, w)

        image = image[top:bottom, left:right, :]
        img_h = bottom - top
        img_w = right - left
        
        delta_h = self.crop_h - img_h
        delta_w = self.crop_w - img_w
        
        if delta_h > 0:
            vert1 = np.zeros([delta_h // 2, img_w, c])
            vert2 = np.zeros([(delta_h + 1) // 2, img_w, c])
            image = np.concatenate((vert1, image, vert2), 0)
    
        if delta_w > 0:   
            hor1 = np.zeros([self.crop_h, delta_w // 2, c])
            hor2 = np.zeros([self.crop_h, (delta_w + 1) // 2, c])
            image = np.concatenate((hor1, image, hor2), 1)
        
        return image


    def get_control_as_input(self, ctrl):
        source_image = self.get_screenshot_as_array()
            
        image = (source_image - 128.0) / 128.0
        common.scroll_to_top(self.driver)
        
        [h, w, _] = image.shape
        top = ctrl.ext_location['y']
        left = ctrl.ext_location['x']
        bottom = top + ctrl.ext_size['height']
        right = left + ctrl.ext_size['width']
        
        top = int(top * self.width_scale)
        left = int(left * self.width_scale) 
        bottom = int(bottom * self.width_scale)
        right = int(right * self.width_scale)
        
        top = max(top, 0)
        left = max(left, 0)
        bottom = min(bottom, h)
        right = min(right, w)

        if top > 20:
            image[:top-20, :, :] = 0
        if bottom + 20 < h:
            image[bottom+20:, :, :] = 0
        if left > 20:
            image[:, :left-20, :] = 0
        if right + 20 < w:
            image[:, right+20:, :] = 0

        image = self.crop_image(image, (left + right) // 2, (top + bottom) // 2)
        
        return image

    
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
            if self.rewards:
                self.rewards.before_action(self.driver, action)
            self.step += 1
            success = action.apply(control, self.driver, self.user)
        except:
            success = False
            traceback.print_exc()
        finally:
            if self.rewards:
                self.rewards.after_action(self.driver, action)
            
        return self.rewards.calc_reward(success) if self.rewards else None
    
    def calc_final_reward(self):
        assert self.rewards is not None

        return self.rewards.calc_final_reward()
