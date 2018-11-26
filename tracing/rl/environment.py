import tempfile
import sys
from PIL import Image
from scipy import misc
import os
import numpy as np
import traceback
import time
import functools

from tracing.rl.actions import Nothing, Wait, Click
import tracing.selenium_utils.common as common
import tracing.selenium_utils.controls as selenium_controls
from tracing.user_data import get_user_data

class Environment:
    
    def __init__(self, 
                 rewards = None, 
                 width = 672, # Width of screenshot
                 headless = True,
                 crop_h = 300,
                 crop_w = 300,
                 crop_pad = 5,
                 max_passes = 3
                ):
        self.rewards = rewards
        self.width = width
        self.headless = headless
        self.step = 0
        self.driver = None
        self.crop_h = crop_h
        self.crop_w = crop_w
        self.screen_scale = None
        self.crop_pad = crop_pad
        self.passes = 0
        self.states = []
        self.max_passes = max_passes

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        self.try_quit_driver()

    def try_quit_driver(self):
        try:
            if self.driver is not None:
                self.driver.quit()
        except:
            traceback.print_exc()

        self.driver = None

    def start(self, url, user_info = None, payment_info = None):
        self.url = url

        if user_info is None or payment_info is None:
            ui, pi = get_user_data()
            user_info = user_info or ui
            payment_info = payment_info or pi

        self.user_info = user_info
        self.payment_info = payment_info


        self.try_quit_driver()
        self.step = 0
        self.controls = None
        self.c_idx = 0
        self.frames = None
        self.f_idx = 0
        self.is_changed = False
        self.passes = 0
        self.states = []

        try:
            self.driver = common.create_chrome_driver(headless = self.headless, size=(1280, 1024))
            self.driver.set_page_load_timeout(120)

            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'http://' + url
        
            self.driver.get(url)
            time.sleep(5)
            self.states.append((url, self.c_idx, self.f_idx))
     
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

    def refresh_controls_if_needs(self):
        if self.passes >= self.max_passes or (self.rewards and self.is_final()) or not self.is_changed:
            return False
           
        return self.reset_control()

    def get_next_control_based_frame(self, url, f_idx, c_idx):
        self.frames = common.get_frames(self.driver)
        self.f_idx = f_idx
        self.try_switch_to_frame()

        self.controls = self.get_controls()
        self.c_idx = c_idx + 1


    def refetch_controls(self):
        url, c_idx, f_idx = self.states[-1]
        
        self.get_next_control_based_frame(url, c_idx, f_idx)

    def reset_control(self):
        self.states = []
        self.try_switch_to_default()

        self.is_changed = False
        self.passes += 1

        self.controls = None
        self.c_ids = 0
        self.frames = None
        self.f_idx = 0

        return True

    def get_next_frame(self, move = True):
        if move:
            self.f_idx += 1

        while True:
            self.try_switch_to_default()
            self.frames = self.get_frames()
            
            if self.f_idx >= len(self.frames):
                return False
            
            if not self.try_switch_to_frame():
                self.f_idx += 1
                continue
            
            self.controls = None
            self.c_idx = 0
            return True

        return True

    def has_next_control(self):
        self.refresh_controls_if_needs()
        
        if self.frames is None:
            # First enter after start
            if not self.get_next_frame(move=False):
                return False

        if self.f_idx >= len(self.frames):
            return False

        # Extract controls from every frame
        while True:
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
            if not self.get_next_frame():
                return False
            
        return False
    

    def get_next_control(self, move = True):
        assert self.has_next_control()
        
        ctrl = self.controls[self.c_idx]
        if move:
            self.c_idx += 1
        
        return ctrl

    def is_final(self):
        assert self.rewards is not None

        return self.rewards.is_final()

    def save_state(self):
        state = (
            common.get_url(self.driver),
            self.c_idx,
            self.f_idx
        )
        self.states.append(state)


    def discard(self):
        assert len(self.states) > 0, "Nothing to discard"
        url, c_idx, f_idx = self.states[-1]

        del self.states[-1]

        if not url.startswith('http://') and not url.startswith('https://'):
           url = 'http://' + url

        self.driver.get(url)
        time.sleep(2)
        self.get_next_control_based_frame(url, c_idx, f_idx)

    # ToDo Need to remove?
    def get_ctrl_by_contains(self, contains, not_contains, type_list):
        ctrl = None

        while True:
            try:
                ctrl = self.get_next_control()
                if ctrl.type not in type_list:
                    continue
                if nlp.check_text(selenium_controls.get_label(ctrl.elem), contains, not_contains):
                    break
            except:
                break
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


    def get_frame_location(self):
        if self.f_idx == 0:
            return {'x': 0, 'y': 0}
        else:
            self.try_switch_to_default()
            if self.f_idx >= len(self.frames):
                print('frames: {}, f_idx: {}, url: {}'.format(len(self.frames), self.f_idx, self.url))

            result = self.frames[self.f_idx].location
            result['y'] -= common.get_scroll_top(self.driver)
            self.try_switch_to_frame()
            return result
    
    
    def get_screen_scale(self, ctrl):
        s = ctrl.size
        self.try_switch_to_default()
        try:
            ws = common.get_viewport_size(self.driver)

            start_scale = self.width / self.crop_w

            scale = max((s['width'] + 2.*self.crop_pad) / ws['width'] * start_scale, 
                    (s['height'] + 2.*self.crop_pad) / ws['height'] * start_scale)

            scale = max(0.5, scale)
            scale = min(start_scale, scale)

            return scale
        finally:
            self.try_switch_to_frame()
    
    
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
        
        frame_offset = self.get_frame_location()

        [h, w, _] = image.shape
        top = y + frame_offset['y']
        left = x + frame_offset['x']
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

    
    def get_controls(self):
        """
        :return:   Returns ordered controls for current frame
        """
        def cmp(ctrl1, ctrl2):
            ydelta = ctrl1.location['y'] - ctrl2.location['y']
            if abs(ydelta) >= 15:
                return ydelta

            return ctrl1.location['x'] - ctrl2.location['x']

        controls = selenium_controls.extract_controls(self.driver)

        # Sort by Top then by Left of control location
        controls.sort(key = functools.cmp_to_key(cmp))

        return controls

    
    def get_frames(self):
        win_height = common.get_page_height(self.driver)
        win_width = self.driver.execute_script('return window.innerHeight')
        
        frames = common.get_frames(self.driver)    
        filtered = []
        for frame in frames:
            if not frame:
                filtered.append(frame)
                continue
                
            if frame.location['x'] < 0 or frame.size['height'] <= 0 or frame.size['width'] <= 0:
                continue
            
            if frame.location['y'] >= win_height - 2:
                continue
        
            if frame.location['x'] >= win_width - 2:
                continue  
            
            filtered.append(frame)
            
        return filtered

    
    def try_switch_to_frame(self):
        try:
            if self.frames and self.f_idx < len(self.frames):
                frame = self.frames[self.f_idx]
                if frame:
                    selenium_controls.scroll_to_element(self.driver, frame)
                    self.driver.switch_to.frame(self.frames[self.f_idx])
 
                return True
        except:
            traceback.print_exc()
        
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
        self.step += 1

        user = [self.user_info, self.payment_info]
        if isinstance(action, Nothing) or isinstance(action, Wait):
            success = action.apply(control, self.driver, user)
            return (success, 0)

        try:
            prev_url = selenium_controls.normalize_url(common.get_url(self.driver))

            if self.rewards:
                self.try_switch_to_default()       
                self.rewards.before_action(self.driver, action)

            if self.rewards:
                 self.try_switch_to_frame()
            success = action.apply(control, self.driver, user)

            url = selenium_controls.normalize_url(common.get_url(self.driver))
            if url != prev_url:
                self.is_changed = True

            if control:
                # Control could disappear track it as Environment Changed
                self.is_changed = self.is_changed or not selenium_controls.is_visible(control.elem)
        except:
            success = False
            traceback.print_exc()

        finally:
            if self.rewards:
                self.try_switch_to_default()

                self.rewards.after_action(self.driver, action)
                self.try_switch_to_frame()
            
        reward = self.rewards.calc_reward(success) if self.rewards else None
        return (success, reward)
                
    def calc_final_reward(self):
        assert self.rewards is not None
        return self.rewards.calc_final_reward()
