from abc import abstractmethod
import random
import tracing.selenium_utils.controls as selenium_controls
import tracing.selenium_utils.common as common
from urllib.parse import urlparse


class IRewardsCalculator:
    
    def start(self, driver):
        pass
    
    def before_action(self, driver, action):
        pass
    
    def after_action(self, driver, action):
        pass
    
    @abstractmethod
    def is_final(self):
        raise NotImplementedError
    
    @abstractmethod
    def calc_reward(self, is_success):
        raise NotImplementedError

    @abstractmethod
    def calc_final_reward(self):
        raise NotImplementedError


class PopupRewardsCalculator(IRewardsCalculator):
    
    def __init__(self):
        self.is_final_state = False
    
    def start(self, driver):
        self.had_popup = False
        self.url = None
        self.have_popup = False
        self.new_url = None
        self.alert_shown = False
        self.is_final_state = not self.is_popup_exists(driver)
    
    
    def is_displayed(self, elem):
        try:
            # Check that location is accessible
            tmp = elem.location
            # Check selenium method is_displayed and that height > 1 and width > 1
            return elem.is_displayed() and elem.size['width'] > 1 and elem.size['height'] > 1
        except:
            return False
    
    def extract_random_controls(self, driver, max_num = 10):
        selects = selenium_controls.get_selects(driver)
        inputs = selenium_controls.get_inputs(driver)
        buttons = selenium_controls.get_buttons(driver)
        links = selenium_controls.get_links(driver)

        checkboxes = selenium_controls.get_checkboxes(driver)
        radios = selenium_controls.get_radiobuttons(driver)
        
        controls = selects + inputs + buttons + links + checkboxes + radios
        visible = [ctrl for ctrl in controls if self.is_displayed(ctrl)]
        
        if len(visible) < max_num:
            return visible
        
        return random.sample(visible, max_num)
    
    def is_popup_exists(self, driver):

        # 1. Scroll to Top
        common.scroll_to_top(driver)

        # 2. Extract visible controls
        controls = self.extract_random_controls(driver, 10)
        
        # 3. Check how many elements are hidden by other elements
        covered = 0
        for ctrl in controls:
            if not selenium_controls.is_visible(ctrl):
                covered += 1

            if covered >= 3:
                return True
        
        return covered >= 3
    
    def get_domain(self, url):
        return urlparse(url).netloc
    
    def is_final(self):
        return self.is_final_state
    
    def before_action(self, driver, action):
        self.alert_shown = False
        self.had_popup = self.is_popup_exists(driver)
        self.url = self.get_domain(driver.current_url)
        
    def after_action(self, driver, action):
        self.alert_shown = common.find_alert(driver)
        if self.alert_shown:
            self.is_final_state = True
            return

        self.have_popup = self.is_popup_exists(driver)
        self.new_url = self.get_domain(driver.current_url)
        self.is_final_state = self.new_url != self.url or not self.have_popup
    
    def calc_reward(self, is_success):
        if self.new_url != self.url or self.alert_shown:
            return 0
        elif self.had_popup and not self.have_popup:
            return 3
        elif not is_success:
            return 0#-1
        else:
            return 0
    
    def calc_final_reward(self):
        if not self.have_popup:
            return 0
        else:
            # Haven't close popup
            return 0#-3

