from abc import abstractmethod
import random
import tracing.selenium_utils.controls as selenium_controls
import tracing.selenium_utils.common as common
from urllib.parse import urlparse
import tempfile
import os


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


class PageRewardsCalculator(IRewardsCalculator):

    @staticmethod
    def for_checkouts(model, cached=True):
        return PageRewardsCalculator(
            model,
            "checkout",
            big_pictures=True,
            reached=True,
            close_alerts=True,
            cached=cached)

    @staticmethod
    def for_popups(model, cached=True):
        return PageRewardsCalculator(
            model,
            "popup",
            big_pictures=False,
            reached=False,
            close_alerts = True,
            cached=cached)

    def __init__(self,
                 model,
                 page_type = "popup",
                 big_pictures = True,
                 reached = True,
                 close_alerts = True,
                 cached = True):
        """
        :param model:     PageClassifier
        :param page_type: "checkout" or "popup"
        :param reached:   Return positive reward if page is reached or disappeared
        :param cached:    If true then rewards are recalculated only after action
        """

        self.model = model
        self.page_type = page_type
        self.big_pictures = big_pictures
        self.reached = reached
        self.close_alerts = close_alerts
        self.cached = cached

        self.goal_proba = 0.
        self.goal_proba_prev = 0.

    def get_domain(self, url):
        return urlparse(url).netloc

    def start(self, driver):
        self.url = self.get_domain(driver.current_url)
        self.new_url = self.url
        self.alert_shown = True if common.find_alert(driver) else False

        self.goal_proba = self.calc_goal_proba(driver)
        self.goal_proba_prev = self.goal_proba
        print('goal proba = ', self.goal_proba)

    def before_action(self, driver, action):
        self.url = self.get_domain(driver.current_url)

        if not self.cached:
            self.goal_proba = self.calc_goal_proba(driver)

    def after_action(self, driver, action):
        self.alert_shown = common.find_alert(driver) is not None
        if self.alert_shown and self.close_alerts:
            common.close_alert_if_appeared(driver)
            self.alert_shown = False

        if self.alert_shown:
            return

        self.new_url = self.get_domain(driver.current_url)

        self.goal_proba_prev = self.goal_proba
        self.goal_proba = self.calc_goal_proba(driver)

    def is_final(self):
        return self.alert_shown or self.new_url != self.url or self.goal_proba > 0.6

    def calc_reward(self, is_success):
        if not self.alert_shown and self.new_url == self.url and self.goal_proba - self.goal_proba_prev > 0.4:
            return 3
        else:
            return 0

    def calc_final_reward(self):
        return 0

    def calc_goal_proba(self, driver):

        # 1. Create tmp file
        fd, tmp_file = tempfile.mkstemp(suffix = '.png')
        file = os.fdopen(fd,'w')
        file.close()

        try:
            # 2. Get screenshot
            common.scroll_to_top(driver)
            if self.big_pictures:
                scale = common.get_scale(driver)
                common.get_full_page_screenshot(driver, tmp_file, scale)
            else:
                common.get_screenshot(driver, tmp_file)

            # 3. Classify page
            page_info = self.model.classify_page(tmp_file)
            proba = page_info[self.page_type]

            if not self.reached:
                proba = 1. - proba

            return proba

        finally:
            # 4. Remove file
            os.remove(tmp_file)


class HeuristicPopupRewardsCalculator(IRewardsCalculator):
    
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
        else:
            return 0
    
    def calc_final_reward(self):
        if not self.have_popup:
            return 0
        else:
            # Haven't close popup
            return 0

