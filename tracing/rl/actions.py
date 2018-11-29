import random

from selenium.webdriver.common.keys import Keys
from tracing.selenium_utils.controls import *
from tracing.selenium_utils import common
from tracing.common_heuristics import *
import uuid

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

    def get_label_not_equals(self):
        """Strings that can't be for control's label"""
        return []

    def get_label_not_contains(self):
        """Strings that can't be as substring of control's label"""
        return ['mail', 'search', 'name', 'country', 'state', 'card', 'zip', 'message', 'text', 'phone']


    def is_applicable(self, ctrl):
        if ctrl.type not in [Types.text, Types.select]:
            return False

        if ctrl.label:
            ctrl_label = ctrl.label.strip().lower()
            for not_equals in self.get_label_not_equals():
                if not_equals == ctrl_label:
                    return False

            for not_contains in self.get_label_not_contains():
                if not_contains in ctrl_label:
                    return False

        if ctrl.type == Types.select:
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
            enter_text(ctrl.elem, self.get_contains()[0])
            time.sleep(5)

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
        return ['01', '1', '20']
    
    def __str__(self):
        return "InputBDay"

    def get_label_not_equals(self):
        return ["month", "year", "input month", "input year", "mm", "yyyy", "email", "input email"]


class InputBMonth(InputBirthday):
    def get_contains(self):
        return ['01', '1', 'January', 'Jan', 'january', 'jan']
    
    def get_not_contains(self):
        return ['13', '28', '31']

    def __str__(self):
        return "InputBMonth"

    def get_label_not_equals(self):
        return ["day", "year", "input day", "input year", "dd", "yyyy", "email", "input email"]


class InputBYear(InputBirthday):
    def get_contains(self):
        return ['1972', '72']

    def __str__(self):
        return "InputBYear"

    def get_label_not_equals(self):
        return ["day", "month", "input day", "input month", "dd", "mm", "email", "input email"]


class InputEmail(IAction):
    def is_applicable(self, ctrl):
        if ctrl.type != Types.text:
            return False

        ctrl_label = ctrl.label
        if not ctrl_label:
            return True

        ctrl_label = ctrl_label.strip().lower()
        if ctrl_label in ['dd', 'mm', 'yyyy', 'day', 'month', 'year']:
            return False

        for not_contains in ['phone', 'search', 'first name', 'last name']:
            if not_contains in ctrl_label:
                return False

        return True

    def apply(self, ctrl, driver, user):
        if self.is_applicable(ctrl):
            email = user[0].email
            if not email:
                second = uuid.uuid4().hex.upper()[0:8] + '@gmail.com'
                email = user.get('email', second)

            enter_text(ctrl.elem, email)
            time.sleep(1)

            return True
        
        return False
    
    def __str__(self):
        return "Input Email"


class InputCheckoutFields(IAction):

    def __init__(self, field):
        self.field = field

    def is_applicable(self, ctrl):
        return ctrl.type in [Types.text]

    def apply(self, ctrl, driver, user):
        if self.is_applicable(ctrl):
            value = 'default'
            if self.field == 'first_name':
                value = user[0].first_name
            elif self.field == 'last_name':
                value = user[0].last_name
            elif self.field == 'street':
                value = user[0].street
            elif self.field == 'zip':
                value = user[0].zip
            elif self.field == 'country':
                value = user[0].country
            elif self.field == 'city':
                value = user[0].city
            elif self.field == 'state':
                value = common.get_name_of_state(user[0].state)
            elif self.field == 'phone':
                value = user[0].phone

            enter_text(ctrl.elem, value)
            time.sleep(1)

            return True

        return False

    def __str__(self):
        return "Input " + self.field


class InputPaymentTextField(IAction):

    def __init__(self, field):
        self.field = field

    def is_applicable(self, ctrl):
        return ctrl.type in [Types.text]

    def apply(self, ctrl, driver, user):
        if self.is_applicable(ctrl):
            value = 'default'
            if self.field == 'card-number':
                value = user[1].card_number
            elif self.field == 'cvc':
                value = user[1].cvc
            elif self.field == 'input-card-month-year':
                value = "{}/{}".format(user[1].expire_date_month, user[1].expire_date_year)
            elif self.field == 'input-card-month':
                value = user[1].expire_date_month
            elif self.field == 'input-card-year':
                value = user[1].expire_date_year

            enter_text(ctrl.elem, value)
            time.sleep(1)

            return True

        return False

    def __str__(self):
        return "Input " + self.field


class InputSelectField(IAction):

    def __init__(self, field):
        self.field = field

    def __str__(self):
        return "InputSelectField " + self.field

    def is_applicable(self, ctrl):
        if ctrl.type not in [Types.select]:
            return False
        return True

    def apply(self, ctrl, driver, user):
        if not self.is_applicable(ctrl):
            return False

        value = None
        months = {"01": 0, "02": 1, "03": 2, "04": 3, "05": 4, "06": 5, "07": 6, "08": 7, "09": 8, "10": 9, "11": 10, "12": 11}
        months_text = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
        months_text_short = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        years = {"18": '2018', "19": '2019', "20": '2020', "21": '2021', "22": '2022', "23": '2023', "24": '2024', "25": '2025', "26": '2026', "27": '2027'}

        if self.field == "select-country-full":
            value = 'United States Of America'
        elif self.field == "select-country-full-short":
            value = 'United States America'
        elif self.field == "select-country-short":
            value = 'United States'
        elif self.field == "select-country-short-form":
            value = 'USA'
        elif self.field == "select-state-name":
            if len(ctrl.values[3]) == 2:
                value = user[0].state
            else:
                value = common.get_name_of_state(user[0].state)
        elif self.field == "card-type":
            value = user[1].card_type
        elif self.field == "expire-month-text-with-number-full":
            index = months.get(user[1].expire_date_month, 0)
            month = months_text[index]
            value = "{} - {}".format(user[1].expire_date_month, month)
            print("expire-month-text-with-number-full ---> {}".format(value))
        elif self.field == "expire-month-text-with-number-short":
            index = months.get(user[1].expire_date_month, 0)
            month = months_text[index]
            value = "{} - {}".format(str(index), month)
            print("expire-month-text-with-number-short ---> {}".format(value))
        elif self.field == "expire-month-text-full":
            index = months.get(user[1].expire_date_month, 1)
            value = months_text[index]
            print("expire-month-text-full ---> {}".format(value))
        elif self.field == "expire-month-text-short":
            index = months.get(user[1].expire_date_month, 1)
            value = months_text_short[index]
            print("expire-month-text-short ---> {}".format(value))
        elif self.field == "expire-month-number-full":
            value = user[1].expire_date_month
            print("expire-month-number-full ---> {}".format(value))
        elif self.field == "expire-month-number-short":
            value = str(months.get(user[1].expire_date_month, 0) + 1)
            print("expire-month-number-short ---> {}".format(value))
        elif self.field == "expire-year-full":
            value = years.get(user[1].expire_date_year, '2020')
        elif self.field == "expire-year-short":
            value = user[1].expire_date_year

        select_combobox_value(driver, ctrl.elem, value)
        time.sleep(1)

        return True


class MarkAsSuccess(IAction):

    def is_applicable(self, ctrl):
        return True

    def apply(self, ctrl, driver, user):
        return True

    def __str__(self):
        return "MarkAsSuccess"


class Click(IAction):
    
    def is_applicable(self, ctrl):
        return ctrl.type in [Types.radiobutton, Types.checkbox, Types.link, Types.button]
        
    def apply(self, ctrl, driver, user):
        if self.is_applicable(ctrl):
            click(driver, ctrl.elem)
            time.sleep(5)

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

    def search_in_google(self, driver, query, site):
        driver.get('https://www.google.com')
        time.sleep(3)

        search_input = driver.find_element_by_css_selector('input.gsfi')
        search_input.clear()
        search_input.send_keys("site:{} {}".format(site, query))
        search_input.send_keys(Keys.ENTER)
        time.sleep(3)

        links = driver.find_elements_by_css_selector('div.g .rc .r > a[href]')
        links = [link.get_attribute("href") for link in links]
        links = list([link for link in links if not link.startswith('https://translate.google.')])

        if len(links) > 0:
            return links
        else:
            return []

    def search_in_bing(self, driver, query, site):
        driver.get('https://www.bing.com')
        time.sleep(3)

        search_input = driver.find_element_by_css_selector('input.b_searchbox')
        search_input.clear()
        search_input.send_keys("site:{} {}".format(site, query))
        search_input.send_keys(Keys.ENTER)
        time.sleep(3)

        links = []
        items = driver.find_elements_by_css_selector("ol#b_results > li.b_algo")
        for item in items:
            if len(item.find_elements_by_css_selector("p strong")) > 0:
                links.append(item.find_element_by_css_selector("h2 > a[href]"))

        if len(links) > 0:
            return [link.get_attribute("href") for link in links]
        else:
            return []


    def filter(self, driver, links):
        for link in links:
            driver.get(link)
            time.sleep(3)
            if len(search_for_add_to_cart(driver)) > 0:
                return link

        return []


    def search_for_product_link(self, driver):
        queries = ['"add to cart"']
        url_domain = driver.current_url.split("/")
        domain = url_domain[0] + "//" + url_domain[2]
        # Open a new tab
        try:
            new_tab(driver)
            for query in queries:
                searches = [self.search_in_bing, self.search_in_google]
                for search in searches:
                    try:
                        links = search(driver, query, domain)
                        link = self.filter(driver, links)

                        if link:
                            return link

                    except:
                        logger = logging.getLogger('shop_tracer')
                        logger.exception('during search in search engine got an exception')

        finally:
            # Close new tab
            close_tab(driver)

        return None

    def apply(self, ctrl, driver, user):
        link = self.search_for_product_link(driver)

        if link:
            driver.get(link)
            time.sleep(3)
            return True

        return False


class InputPassword(IAction):
    def apply(self, control, driver, user):
        if not self.is_applicable(control):
            return False

        # Generate password that secure
        text = str(uuid.uuid4())[0:4].upper() + '_' + '912' + str(uuid.uuid4())[:4].lower()
        enter_text(control.elem, text)
        time.sleep(1)

        return True

    def is_applicable(self, control):
        if control.type not in [Types.text]:
            return False

        label = (control.label or '').strip().lower()
        if label:
            return label.find('password') >= 0

        return True


class SelectFirst(IAction):
    def apply(self, control, driver, user):
        if not self.is_applicable(control):
            return False

        values = control.values
        if len(values) == 0:
            return False

        if len(values) == 1:
            val = values[0]
        else:
            val = values[1]

        select_combobox_value(driver, control.elem, val)
        time.sleep(1)

        return True

    def is_applicable(self, control):
        return control.type in [Types.select]


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

    # Actions that are used to close Popups
    popups = [InputBDay(), InputBMonth(), InputBYear(), Click(), InputEmail(), Nothing()]

    # Actions that are used for navigation to Checkout Page
    # ToDo Login??
    navigation = [Click(), InputEmail(), InputPassword(), SelectFirst(), Nothing()]

