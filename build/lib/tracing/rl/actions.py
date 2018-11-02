import random

from selenium.webdriver.common.keys import Keys
from tracing.selenium_utils.controls import *
from abc import abstractmethod

class IAction:
    
    @abstractmethod
    def apply(self, control, driver, user):
        """
        Returns True or False if action was applied successfuly
        """
        raise NotImplementedError()

    @abstractmethod
    def is_applicable(self, control):
        """
        Returns True or False whether the action could be applied to control
        """
        raise NotImplementedError()


class ISiteAction:
    
    @abstractmethod
    def apply(self, driver, user):
        """
        Returns True or False if action was applied successfuly
        """
        raise NotImplementedError()

    @abstractmethod
    def is_applicable(self, driver):
        """
        Returns True or False whether the action could be applied to control
        """
        raise NotImplementedError()


class InputBirthday(IAction):
    @abstractmethod
    def get_contains(self):
        raise NotImplementedError()

    def get_not_contains(self):
        return []
    
    def is_applicable(self, ctrl):
        if ctrl.type not in [Types.text, Types.select]:
            return False
        
        if ctrl.type != Types.text:
            val = None
            for txt in self.get_contains():
                if txt in ctrl.values:
                    val = txt
                    
            if val is None:
                return False

            for txt in self.get_not_contains():
                if txt in ctrl.values:
                    return False

        return True
    
    def apply(self, ctrl, driver, user):
        if not self.is_applicable(ctrl):
            return False
                
        if ctrl.type == Types.text:
            enter_text(driver, ctrl.elem, self.get_contains()[0])
            time.sleep(1)

        else:
            val = None
            for txt in self.get_contains():
                if txt in ctrl.values:
                    val = txt

            if val is None:
                return False

            select_combobox_value(driver, ctrl.elem, val)
            time.sleep(1)

        return True
    
class InputBDay(InputBirthday):
    def get_contains(self):
        return ['1', '01'] 
    
    def __str__(self):
        return "InputBDay"

    
class InputBMonth(InputBirthday):
    def get_contains(self):
        return ['01', '1', 'January', 'Jan', 'january', 'jan']
    
    def get_not_contains(self):
        return ['13', '28', '31']

    def __str__(self):
        return "InputBMonth"


class InputBYear(InputBirthday):
    def get_contains(self):
        return ['1972', '72']

    def __str__(self):
        return "InputBYear"


class InputEmail(IAction):
    def is_applicable(self, ctrl):
        return ctrl.type in [Types.text]
        
    def apply(self, ctrl, driver, user):
        if self.is_applicable(ctrl):
            email = user.get('email', 'test@gmail.com')

            enter_text(driver, ctrl.elem, email)
            time.sleep(1)

            return True
        
        return False
    
    def __str__(self):
        return "Input Email"


class Click(IAction):
    
    def is_applicable(self, ctrl):
        return ctrl.type in [Types.radiobutton, Types.checkbox, Types.link, Types.button]
        
    def apply(self, ctrl, driver, user):
        if self.is_applicable(ctrl):
            click(driver, ctrl.elem)
            time.sleep(1)
            return True
        
        return False
    
    def __str__(self):
        return "Click"

    
class Wait(IAction):
    def is_applicable(self, ctrl):
        return True

    def apply(self, ctrl, driver, user):
        time.sleep(2)
        return True
    
    def __str__(self):
        return "Wait"


class Nothing(IAction):
    def is_applicable(self, ctrl):
        return True

    def apply(self, ctrl, driver, user):
        return True
    
    def __str__(self):
        return "Do Nothing"


class SearchProductPage(ISiteAction):
    def is_applicable(self, driver):
        return True

    def search_in_google(self, driver, query):
        driver.get('https://www.google.com')
        time.sleep(3)

        search_input = driver.find_element_by_css_selector('input.gsfi')
        search_input.clear()
        search_input.send_keys(query)
        search_input.send_keys(Keys.ENTER)
        time.sleep(3)

        links = driver.find_elements_by_css_selector('div.g .rc .r a[href]')
        if len(links) > 0:
            return [link.get_attribute("href") for link in links]
        else:
            return None

    def search_in_bing(self, driver, query):
        driver.get('https://www.bing.com')
        time.sleep(3)

        search_input = driver.find_element_by_css_selector('input.b_searchbox')
        search_input.clear()
        search_input.send_keys(query)
        search_input.send_keys(Keys.ENTER)
        time.sleep(3)
        
        links = driver.find_elements_by_css_selector('ol#b_results > li.b_algo > h2 > a[href]')
        
        if len(links) > 0:
            return [link.get_attribute("href") for link in links]
        else:
            return None

    def search_for_product_link(self, driver):
        queries = ['"add to cart"']
        url_domain = driver.current_url.split("/")
        domain = url_domain[0] + "//" + url_domain[2]
        # Open a new tab
        try:
            new_tab(driver)
            for query in queries:
                google_query = 'site:{} {}'.format(domain, query)

                searches = [self.search_in_bing, self.search_in_google]
                for search in searches:
                    try:
                        links = search(driver, google_query)
                        if links:
                            return links

                    except:
                        logger = logging.getLogger('shop_tracer')
                        logger.exception('during search in search engine got an exception')

        finally:
            # Close new tab
            close_tab(driver)

        return links

    def apply(self, ctrl, driver, user):
        links = self.search_for_product_link(driver)

        if links:
            links = list(links)

            driver.get(links[0])
            time.sleep(3)
            return True
        return False


class Actions:
    actions = [
        InputBDay(),
        InputBMonth(),
        InputBYear(),
        Click(),
        Wait(),
        SearchProductPage(),
        InputEmail(),
        Nothing()
    ]

