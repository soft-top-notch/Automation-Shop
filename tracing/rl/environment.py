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
    
    def __init__(self, 
                 rewards = None, 
                 user = None, 
                 width = 672, # Width of screenshot
                 headless = True,
                 crop_h = 300,
                 crop_w = 300,
                 crop_pad = 5
                ):
        self.rewards = rewards
        self.user = user
        self.width = width
        self.headless = headless
        self.step = 0
        self.driver = None
        self.crop_h = crop_h
        self.crop_w = crop_w
        self.screen_scale = None
        self.crop_pad = crop_pad

    def __enter__(self):
        pass

    def is_final(self):
        assert self.rewards is not None

        return self.rewards.is_final()
    

    def start(self, url):
        self.step = 0
        self.controls = None
        self.c_idx = 0
        self.frames = None
        self.f_idx = 0

        try:
            if not self.driver:
                self.driver = common.create_chrome_driver(headless = self.headless, size=(1280, 1024))
                self.driver.set_page_load_timeout(120)

            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'http://' + url
        
            self.driver.get(url)
            time.sleep(5)
     
            if self.rewards:
                self.rewards.start(self.driver)

            if self.screen_scale is None:
                self.screen_scale = common.get_scale(self.driver)

            if self.rewards:
                return not self.rewards.is_final()
            else:
                return True
        
        except:
            traceback.print_exc()
            return False

    
    def __exit__(self, type, value, traceback):
        self.try_quit_driver()


    def try_quit_driver(self):
        try:
            if self.driver is not None:
                self.driver.quit()
        except:
            traceback.print_exc()

        self.driver = None


    def has_next_control(self):
        if self.frames is None:
            # First enter after start
            self.frames = common.get_frames(self.driver)
            self.f_idx = 0
            self.controls = None

        # Extract controls from every frame
        while self.f_idx < len(self.frames):
            if self.controls is None:
                self.controls = self.get_controls()
                self.c_idx = 0
        
            while self.c_idx < len(self.controls):
                ctrl = self.controls[self.c_idx]
                if not common.is_stale(ctrl.elem) and selenium_controls.is_visible(ctrl.elem):
                    return True
    
                self.c_idx += 1

            self.controls = None
            
            # Finding for the next frame
            self.f_idx += 1
            while self.f_idx < len(self.frames):
                self.try_switch_to_default()
                if self.try_switch_to_frame():
                    break
                    
                self.f_idx += 1

        return False
    

    def get_next_control(self, move = True):
        assert self.has_next_control()
        
        ctrl = self.controls[self.c_idx]
        if move:
            self.c_idx += 1
        
        return ctrl


    # Returns 3D Numpy array of image representation
    # Channels x Width X Height
    def get_screenshot_as_array(self, full_page = False, scale = 1.):
        assert self.driver is not None
        
        # 1. Create temp file
        f, tmp = tempfile.mkstemp(suffix='.png')
        os.close(f)

        # 2. Take a screenshot
        if full_page:
            common.get_full_page_screenshot(self.driver, tmp, self.screen_scale)    
        else:
            common.get_screenshot(self.driver, tmp)

        # 3. Resize image
        img = Image.open(tmp)
        width_scale = self.width / float(img.size[0]) / scale

        width = int(self.width / scale)
        height = int((img.size[1] * width_scale))
        img = img.resize((width, height), Image.ANTIALIAS)
        img.save(tmp)
        
        self.scale = width_scale * self.screen_scale
        

        # 4. Read as a numpy array
        image = misc.imread(tmp)
        os.remove(tmp)
        
        image = image[:, :, :3]
        [h, w, _] = image.shape
        if h < w:
            to_add = np.ndarray([w-h, w, 3], dtype=np.uint8)
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
            if delta_h > 1:
                vert1 = np.zeros([delta_h // 2, img_w, c])
            vert2 = np.zeros([(delta_h + 1) // 2, img_w, c])
            
            if delta_h == 1:
                image = np.concatenate((image, vert2), 0)
            else:
                image = np.concatenate((vert1, image, vert2), 0)
    
        if delta_w > 0:   
            if delta_w > 1:
                hor1 = np.zeros([self.crop_h, delta_w // 2, c])
            hor2 = np.zeros([self.crop_h, (delta_w + 1) // 2, c])
            
            if delta_w == 1:
                image = np.concatenate((image, hor2), 1)
            else:
                image = np.concatenate((hor1, image, hor2), 1)
            
        
        return image


    def get_screen_scale(self, ctrl):
        s = ctrl.size
        ws = common.get_viewport_size(self.driver)

        start_scale = self.width / self.crop_w

        scale = max((s['width'] + 2.*self.crop_pad) / ws['width'] * start_scale, 
                    (s['height'] + 2.*self.crop_pad) / ws['height'] * start_scale)

        scale = max(0.5, scale)
        scale = min(start_scale, scale)

        return scale

    
    def get_control_as_input(self, ctrl):
        x, y = selenium_controls.scroll_to_element(self.driver, ctrl)
        if y < 0:
            for i in range(5):
                # Try to scroll 1000 pixels lower if it's a hidden menu item
                common.scroll_to(self.driver, 200 * i)
                time.sleep(0.1)
                if ctrl.location['y'] >= 0:
                    scroll = common.get_scroll_top(self.driver)
                    y = ctrl.location['y'] - scroll
                    x = ctrl.location['x']
                
        
        assert ctrl.location['y'] >= 0
        
        time.sleep(0.2)
        
        scale = self.get_screen_scale(ctrl)
        image = self.get_screenshot_as_array(scale=scale)
        
        [h, w, _] = image.shape
        top = y              
        left = x
        bottom = top + ctrl.size['height']
        right = left + ctrl.size['width']
        
        top = int(top * self.scale)
        left = int(left * self.scale) 
        bottom = int(bottom * self.scale)
        right = int(right * self.scale)
        
        top = max(top, 0)
        left = max(left, 0)
        bottom = min(bottom, h)
        right = min(right, w)
        
        assert(bottom > top and right > left)

        if top > self.crop_pad:
            image[:top-self.crop_pad, :, :] = 0
        if bottom + self.crop_pad < h:
            image[bottom+self.crop_pad:, :, :] = 0
        if left > self.crop_pad:
            image[:, :left-self.crop_pad, :] = 0
        if right + self.crop_pad < w:
            image[:, right+self.crop_pad:, :] = 0

        image = self.crop_image(image, (left + right) // 2, (top + bottom) // 2)
        
        return (image - 128.0) / 128.0

    
    # Returns input images for different controls
    def get_controls(self):
        
        controls = selenium_controls.extract_controls(self.driver)

        # Sort by Top then by Left of control location
        controls.sort(key = lambda ctrl: (ctrl.location['y'], ctrl.location['x']))
        
        return controls

    
    def try_switch_to_frame(self):
        try:
            if self.frames and self.f_idx < len(self.frames):
                frame = self.frames[self.f_idx]
                if frame:
                    self.driver.switch_to.frame(self.frames[self.f_idx])
 
                return True
        except:
            pass
        
        return False

    
    def try_switch_to_default(self):
        try:
            self.driver.switch_to.default_content()
            return True
        except:
            return False
            
    
    def apply_action(self, control, action):
        # Switch to main frame 
        success = False
        try:
            if self.rewards:
                self.try_switch_to_default()       
                self.rewards.before_action(self.driver, action)
            self.step += 1

            if self.rewards:
                 self.try_switch_to_frame()
            success = action.apply(control, self.driver, self.user)
        except:
            success = False
            traceback.print_exc()

        finally:
            if self.rewards:
                self.try_switch_to_default()       

                self.rewards.after_action(self.driver, action)
                self.try_switch_to_frame()
            
        return self.rewards.calc_reward(success) if self.rewards else None
    
    def calc_final_reward(self):
        assert self.rewards is not None

        return self.rewards.calc_final_reward()
