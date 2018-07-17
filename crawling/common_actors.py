from shop_crawler import *
from selenium_helper import *
from common_heuristics import *

import nlp
import random
import sys
import traceback
import time
import calendar

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import ElementNotVisibleException, TimeoutException


def wait_until_attribute_disappear(driver, attr_type, attr_name):
    try:
        if attr_type == "id":
            element = WebDriverWait(driver, 2).until(
                EC.invisibility_of_element_located((By.ID, attr_name))
            )
        elif attr_type == "name":
                element = WebDriverWait(driver, 2).until(
                    EC.invisibility_of_element_located((By.NAME, attr_name))
                )
    except TimeoutException:
        print('The element does not disappear')
        return False

    return True


class ToProductPageLink(IStepActor):
    def get_states(self):
        return [States.new, States.shop]

    @staticmethod
    def find_to_product_links(driver):
        return find_links(driver, ['/product', '/commodity', '/drug', 'details', 'view'])

    @staticmethod
    def process_links(driver, state, links):
        if not links:
            return state
        
        attempts = 3
        links = list(links)
        random.shuffle(links)

        for i in range(attempts):
            if i >= len(links):
                break

            link = links[i]

            url = ShopCrawler.normalize_url(link)
            driver.get(url)
            time.sleep(5)
            
            # Check that have add to cart buttons
            if AddToCart.find_to_cart_elements(driver):
                return States.product_page
            else:
                back(driver)

        return state
    
    def process_page(self, driver, state, context):
        links = list([link.get_attribute('href') for link in ToProductPageLink.find_to_product_links(driver)])
        return ToProductPageLink.process_links(driver, state, links)

    
class AddToCart(IStepActor):
    def get_states(self):
        return [States.new, States.shop, States.product_page]

    @staticmethod
    def find_to_cart_elements(driver):
        return find_buttons_or_links(driver, ["addtocart", 
                                              "addtobag", 
                                              "add to cart",
                                              "add to bag"], ['where'])
        
    def process_page(self, driver, state, context):
        elements = AddToCart.find_to_cart_elements(driver)

        if click_first(driver, elements, try_handle_popups, randomize = True):
            time.sleep(5)
            return States.product_in_cart
        else:
            return state


class ToShopLink(IStepActor):
    def get_states(self):
        return [States.new]

    def find_to_shop_elements(self, driver):
        return find_buttons_or_links(driver, ["shop", "store", "products"], ["shops", "stores", "shopping"])

    def process_page(self, driver, state, context):
        elements = self.find_to_shop_elements(driver)
        if click_first(driver, elements, try_handle_popups):
            return States.shop
        else:
            return state


class ToCartLink(IStepActor):
    def find_to_cart_links(self, driver):
        return find_links(driver, ["cart"], ['add', 'append'])

    def get_states(self):
        return [States.product_in_cart]

    def process_page(self, driver, state, context):

        attempts = 3
        for attempt in range(attempts):
            btns = self.find_to_cart_links(driver)

            if len(btns) <= attempt:
                break

            if click_first(driver, btns, randomize = True):
                time.sleep(5)
                checkouts = ToCheckout.find_checkout_elements(driver)

                if not is_empty_cart(driver) and len(checkouts) > 0:
                    return States.cart_page
                else:
                    back(driver)


        return state


class ToCheckout(IStepActor):

    @staticmethod
    def find_checkout_elements(driver):
        contains =  ["checkout", "check out"]
        not_contains = ['guest', 'continue shopping', 'return']
        btns = find_buttons_or_links(driver, contains, not_contains)

        # if there are buttongs that contains words in text return them first
        exact = []
        for btn in btns:
            text = btn.get_attribute('innerHTML')
            if nlp.check_text(text, contains, not_contains):
                exact.append(btn)

        if len(exact) > 0:
            return exact

        return btns

    def get_states(self):
        return [States.product_in_cart, States.cart_page]

    
    @staticmethod
    def has_checkout_btns(driver):
        btns = ToCheckout.find_checkout_elements(driver)
        return len(btns) > 0

    
    @staticmethod
    def process(driver, state, max_depth=3):
        btns = ToCheckout.find_checkout_elements(driver)

        if click_first(driver, btns):
            time.sleep(5)
            if not is_empty_cart(driver):
                if ToCheckout.has_checkout_btns(driver) and max_depth > 0:                    
                    ToCheckout.process(driver, state, max_depth - 1)
                
                return States.checkout_page

        return state
    
    def process_page(self, driver, state, context):
        return ToCheckout.process(driver, state)


class PaymentFields(IStepActor):
    def get_states(self):
        return [States.checkout_page]

    def find_pwd_in_checkout(self, driver):
        pwd_inputs = driver.find_elements_by_css_selector("input[type='password']")

        return pwd_inputs

    def find_auth_pass_elements(self, driver):
        return find_radio_or_checkbox_buttons(driver, ["guest", "create*.*later"])

    def filter_page(self, driver, state, content):
        password_fields = self.find_pwd_in_checkout(driver)
        logger = logging.getLogger("shop_crawler")
        if password_fields:
            if password_fields[0].is_displayed():
                if not self.find_auth_pass_elements(driver):
                    logger.debug("We can't use this url! Login password required!")
                    return False

        return True

    def get_label_text_with_attribute(self, driver, elem):
        label_txt = ""
        element_attribute = get_element_attribute(elem)

        if element_attribute:
            label = driver.find_elements_by_css_selector("label[for='%s']" % element_attribute[1])
            if label:
                label_txt = nlp.remove_elements(label[0].text, ["/", "*", "-", "_", ":", " "]).lower()
            else:
                label_txt = nlp.remove_elements(
                    element_attribute[1],
                    ["/", "*", "-", "_", ":", " "]
                ).lower()

        return label_txt

    def find_select_element(self, driver, contain, consider_contain=None):
        selects = driver.find_elements_by_css_selector("select")
        result = None
        pass_once = False
        content = contain

        if consider_contain:
            if content == consider_contain[0]:
                content = consider_contain[1]
                pass_once = True

        for sel in selects:
            label_text = self.get_label_text_with_attribute(driver, sel)

            if nlp.check_text(label_text, [content]):
                if pass_once:
                    pass_once = False
                    continue
                result = sel
                break
        return result

    def process_select_option(self, driver, contains, context):
        result_cnt = 0
        for item in contains:
            sel = self.find_select_element(driver, item, ['exp1', 'exp'])
            if not sel:
                continue
            for option in sel.find_elements_by_css_selector("option"):
                if nlp.check_text(option.text, [
                        nlp.normalize_text(context.user_info.state),
                        nlp.normalize_text(context.user_info.country),
                        nlp.normalize_text(context.payment_info.card_type),
                        str(context.payment_info.expire_date_year),
                        nlp.normalize_text(calendar.month_abbr[context.payment_info.expire_date_month]),
                        str(context.payment_info.expire_date_month)
                    ]):
                    option.click() # select() in earlier versions of webdriver
                    time.sleep(2)
                    result_cnt += 1
                    break
        return result_cnt > 0

    def input_fields_in_checkout(self,
                                 driver,
                                 context,
                                 select_contains,
                                 extra_contains,
                                 is_userInfo=True,
                                 not_extra_contains=None):
        logger = logging.getLogger('shop_crawler')
        success_flag = False

        if not self.process_select_option(driver, select_contains, context):
            logger.debug("Not found select options!")

        input_texts = driver.find_elements_by_css_selector("input[type='text']")
        input_texts += driver.find_elements_by_css_selector("input[type='email']")

        if is_userInfo:
            json_Info = context.user_info.get_json_userinfo()
        else:
            json_Info = context.payment_info.get_json_paymentinfo()

        for elem in input_texts:
            label_text = self.get_label_text_with_attribute(driver, elem)

            if not label_text:
                continue

            for conItem in extra_contains:
                if nlp.check_text(label_text, conItem[0].split(","), not_extra_contains):
                    label_text = conItem[1]
                    break
            for key in json_Info.keys():
                if nlp.check_text(label_text, [nlp.remove_elements(key, [" "])]):
                    try:
                        elem.click()
                        elem.send_keys(json_Info[key])
                        success_flag = True
                    except:
                        pass
                    break
        return success_flag

    def fill_billing_address(self, driver, context):
        select_contains = ["country", "state", "zone"]
        not_extra_contains = ["email"]
        extra_contains = [
            ["address", "street"], # First item is a sub-string to check in text, Second item is a string to add in text
            ["post", "zip"]
        ]

        return self.input_fields_in_checkout(
            driver,
            context,
            select_contains,
            extra_contains,
            True,
            not_extra_contains
        )

    def fill_payment_info(self, driver, context):
        select_contains = ["card", "exp", "exp1"]
        not_extra_contains = ["first", "last", "phone"]
        extra_contains = [
            ["owner", "name"],
            ["cc.*n", "number"],
            ["verif*,secur*,cv,ccc", "cvc"]
        ]
        return self.input_fields_in_checkout(
            driver,
            context,
            select_contains,
            extra_contains,
            False
        )

    def click_one_element(self, elements):
        for element in elements:
            if element.is_displayed():
                try:
                    element.click()
                    time.sleep(3)
                    return True
                except:
                    pass
        return False

    def click_to_order(self, driver, context):
        logger = logging.getLogger('shop_crawler')
        dest = []
        is_paymentinfo = True
        payment_url = None

        while True:
            order = find_buttons(
                driver,
                ["order", "checkout"]
            )

            agree_btns = find_radio_or_checkbox_buttons(
                driver,
                ["agree", "terms", "paypal"],
                ["express"]
            )

            if agree_btns:
                for elem in agree_btns:
                    if not elem.is_selected():
                        try:
                            elem.click()
                            break
                        except ElementNotVisibleException:
                            pass
            if order:
                break

            continue_btns = find_buttons_or_links(driver, ["continue"], ["login"])
            flag = False

            if continue_btns:
                try:
                    continue_btns[len(continue_btns) - 1].click()
                except:
                    flag = True
                    pass
            if flag or not continue_btns:
                forward_btns = find_buttons_or_links(driver, ["bill", "proceed"])
                if not forward_btns:
                    logger.debug("Step over error")
                    return False
                forward_btns[len(forward_btns) - 1].click()
            time.sleep(2)

        if not self.fill_payment_info(driver, context):
            is_paymentinfo = False

        if order[0].get_attribute('href'):
            payment_url = order[0].get_attribute('href')

        '''paying or clicking place order for paying...'''

        order_attribute = get_element_attribute(order[0])
        order[0].click()
        time.sleep(2)

        if order_attribute[0] != "value":
            if wait_until_attribute_disappear(driver, order_attribute[0], order_attribute[1]):
                logger.debug("Order element is disappeared")
        else:
            time.sleep(2)

        '''paying if payment info is not inputed'''
        if payment_url:
            driver.get(payment_url)
        if not is_paymentinfo:
            if not self.fill_payment_info(driver, context):
                return False
            pay_button = find_buttons_or_links(
                driver,
                ["pay"]
            )
            return self.click_one_element(pay_button)

        return True

    def process_page(self, driver, state, context):
        #the case if authentication is requiring, pass authentication by creating an account as guest...
        auth_pass = self.find_auth_pass_elements(driver)
        if auth_pass:
            #create an account as guest....
            if not click_first(driver, auth_pass):
                return state
            account_btn = find_buttons_or_links(driver, ["button*.*account", "account*.*button"])
            if account_btn:
                if click_first(driver, account_btn):
                    time.sleep(2)

        #the case if authentication is not requiring....
        if not self.fill_billing_address(driver, context):
            return state
        if not self.click_to_order(driver, context):
            return state

        return States.purchased

    
class SearchForProductPage(IStepActor):

    def get_states(self):
        return [States.new, States.shop]
        
    def search_in_google(self, driver, query):
        driver.get('https://www.google.com')
        time.sleep(1)

        search_input = driver.find_element_by_css_selector('input.gsfi')
        search_input.clear()
        search_input.send_keys(query)
        search_input.send_keys(Keys.ENTER)
        time.sleep(2)

        links = driver.find_elements_by_css_selector('div.g .rc .r a[href]')
        if len(links) > 0:
            return [link.get_attribute("href") for link in links]
        else:
            return None

    def search_in_bing(self, driver, query):
        driver.get('https://www.bing.com')
        time.sleep(1)

        search_input = driver.find_element_by_css_selector('input.b_searchbox')
        search_input.clear()
        search_input.send_keys(query)
        search_input.send_keys(Keys.ENTER)
        time.sleep(2)
        
        links = driver.find_elements_by_css_selector('ol#b_results > li.b_algo > h2 > a[href]')
        
        if len(links) > 0:
            return [link.get_attribute("href") for link in links]
        else:
            return None

    def search_for_product_link(self, driver, domain):
        queries = ['"add to cart"']

        links = None
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
                        logger = logging.getLogger('shop_crawler')
                        logger.exception('during search in search engine got an exception')

        finally:
            # Close new tab
            close_tab(driver)

        return links

    def process_page(self, driver, state, context):
        links = self.search_for_product_link(driver, context.domain)

        if links:
            return ToProductPageLink.process_links(driver, state, links)
        
        return state


def add_crawler_extensions(crawler):
    crawler.add_handler(AddToCart(), 4)
    crawler.add_handler(SearchForProductPage(), 1)
    crawler.add_handler(ToProductPageLink(), 3)
    crawler.add_handler(ToShopLink(), 2)

    crawler.add_handler(ToCheckout(), 3)
    crawler.add_handler(ToCartLink(), 2)
    crawler.add_handler(PaymentFields(), 2)
