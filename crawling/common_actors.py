from shop_crawler import *
from selenium_helper import *
import nlp

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import WebDriverException

import sys
import re
import traceback
import time


def is_empty_cart(driver):
    text = get_page_text(driver)
    return nlp.check_if_empty_cart(text)


def can_click(element):
    try:
        element.is_enabled();
        return element.is_displayed()
    except WebDriverException:
        logger = logging.getLogger('shop_crawler')
        logger.debug('Exception during checking element {}'.format(traceback.format_exc()))
        return False
        

def find_in_elems(elements, contains=None, not_contains=None):
    result = []
    for elem in elements:
        if not can_click(elem):
            continue

        text = elem.get_attribute("outerHTML")
        if nlp.check_text(text, contains, not_contains):
            result.append(elem)

    return result


def find_buttons_or_links(driver,
                          contains=None,
                          not_contains=None):
    links = driver.find_elements_by_css_selector("a[href]")
    buttons = driver.find_elements_by_css_selector("button")
    inputs = driver.find_elements_by_css_selector('input[type="button"]')
    submits = driver.find_elements_by_css_selector('input[type="submit"]')

    # Yield isn't good because context can change

    return find_in_elems((links + buttons + inputs + submits), contains, not_contains)


def find_radio_or_checkout_btns(driver, contains=None, not_contains=None):
    radiobtns = driver.find_elements_by_css_selector("input[type='radio']")
    checkbtns = driver.find_elements_by_css_selector("input[type='checkbox']")
    inputs = driver.find_elements_by_css_selector('input[type="button"]')
    buttons = driver.find_elements_by_css_selector("buttons")

    return find_in_elems((radiobtns + checkbtns + inputs + buttons), contains, not_contains)

def find_selects(driver, contains=None, not_contains=None):
    selects = driver.find_elements_by_tag_name("select")
    return find_in_elems(selects, contains, not_contains)

def find_links(driver, contains=None, not_contains=None, by_path=False):
    links = driver.find_elements_by_css_selector("a[href]")
    result = []
    for link in links:
        if not can_click(link):
            continue

        href = link.get_attribute("href")
        if driver.current_url == href:
            continue

        if by_path:
            text = link.get_attribute("href")
        else:
            text = link.get_attribute("outerHTML")

        if nlp.check_text(text, contains, not_contains):
            result.append(link)

    return result

def to_string(element):
    try:
        return element.get_attribute('outerHTML')
    except:
        return str(element)


def click_first(driver, elements, on_error=None):
    def process(element):
        try:
            # process links by opening url
            href = element.get_attribute("href")
            if href and driver.current_url != href:
                driver.get(href)
                return True

            ActionChains(driver).move_to_element(element).perform()

            old_windows = len(driver.window_handles)
            element.click()
            new_windows = len(driver.window_handles)

            if new_windows > old_windows:
                driver.switch_to_window(driver.window_handles[-1])

            return True
        
        except WebDriverException:
            logger = logging.getLogger('shop_crawler')
            logger.debug('Unexpected exception during clicking element {}'.format(traceback.format_exc()))
            return False

    logger = logging.getLogger('shop_crawler')
            
    for element in elements:
        clicked = process(element)
        logger.debug('clicking, result = {}, element = {}'.format(clicked, to_string(element)))
                     
        if clicked:
            return True

        if on_error and on_error(driver):
            if process(element):
                return True

    return False


def try_handle_popups(driver):
    btns = find_buttons_or_links(driver, ["i .*over", "i .*age", ".* agree .*"], [' .*not.*', " .*under.*"])
    return click_first(driver, btns)

def tokenize(text):
    return re.split(r'(\d+|\W+)', text)

class ToProductPageLink(IStepActor):
    def get_states(self):
        return [States.new, States.shop]

    def find_to_product_links(self, driver):
        return find_links(driver, ['/product', '/commodity', '/drug'], by_path=True)

    def process_page(self, driver, state, context):
        links = self.find_to_product_links(driver)
        if click_first(driver, links):
            return States.product_page
        else:
            return state


class AddToCart(IStepActor):
    def get_states(self):
        return [States.new, States.shop, States.product_page]

    def filter_button(self, button):
        text = button.get_attribute('innerHTML')
        words = tokenize(text)
        if 'buy' in words:
            return len(words) <= 2
        
        return True
        
    def find_to_cart_elements(self, driver):
        btns = find_buttons_or_links(driver, ["add to cart",
                                              "add to bag",
                                              "buy"
                                              ])
        return list([btn for btn in btns if self.filter_button(btn)])

    def process_page(self, driver, state, context):
        elements = self.find_to_cart_elements(driver)
        if click_first(driver, elements, try_handle_popups):
            return States.product_in_cart
        else:
            return state


class ToShopLink(IStepActor):
    def get_states(self):
        return [States.new]

    def find_to_shop_elements(self, driver):
        return find_buttons_or_links(driver, ["shop", "store", "products"], ["shops", "stores"])

    def process_page(self, driver, state, context):
        elements = self.find_to_shop_elements(driver)
        if click_first(driver, elements, try_handle_popups):
            return States.shop
        else:
            return state


class ToCartLink(IStepActor):
    def find_to_cart_links(self, driver):
        return find_links(driver, ["cart"], ['add', 'append'], by_path=True)

    def get_states(self):
        return [States.product_in_cart]

    def process_page(self, driver, state, context):
        btns = self.find_to_cart_links(driver)

        if click_first(driver, btns) and not is_empty_cart(driver):
            return States.cart_page
        else:
            return state


class ToCheckout(IStepActor):

    def find_checkout_elements(self, driver):
        return find_buttons_or_links(driver, ["checkout", "check out"])

    def get_states(self):
        return [States.product_in_cart, States.cart_page]

    def process_page(self, driver, state, context):
        btns = self.find_checkout_elements(driver)

        if click_first(driver, btns) and not is_empty_cart(driver):
            return States.checkout_page
        else:
            return state


class PaymentFields(IStepActor):

    def get_states(self):
        return [States.checkout_page]

    def find_pwd_in_checkout(self, driver):
        pwd_inputs = driver.find_elements_by_css_selector("input[type='password']")

        return len(pwd_inputs) > 0

    def find_auth_pass_elements(self, driver):
        return find_radio_or_checkout_btns(driver, ["guest", "create*.*later"])

    def select_country_or_state(self, driver, contains, context):
        succss_cnt = 0
        for item in contains:
            selects = find_selects(driver, [item])
            for elem in selects:
                flg_cnt = False
                for option in elem.find_elements_by_tag_name("option"):
                    if option.text == context.user_info.state or option.text == context.user_info.country:
                        option.click() # select() in earlier versions of webdriver
                        time.sleep(2)
                        flg_cnt = True
                        break
                if flg_cnt:
                    succss_cnt += 1
                    break
        return succss_cnt > 0

    def fill_billing_address(self, driver, context):
        logger = logging.getLogger('shop_crawler')

        if not self.select_country_or_state(driver, ["country, state"], context):
            logger.debug('Country or State is not correct: country = {}, state = {}'.
                format(
                    context.user_info.country,
                    context.user_info.state
                )
            )
            return False

        input_texts = driver.find_elements_by_css_selector("input[type='text']")
        json_userInfo = context.user_info.json_userInfo()

        for elem in input_texts:
            label_txt = ""

            if not self.get_elem_attribute(elem, ["id", "name"]):
                continue
            elif elem.get_attribute("id"):
                label = driver.find_elements_by_css_selector("label[for='%s']" % elem.get_attribute("id"))
                if not label:
                    continue
                label_txt = nlp.remove_elements(label[0].text, ["/", "*", "-", "_", ":", " "]).lower()
            elif elem.get_attribute("name"):
                label_txt = nlp.remove_elements(elem.get_attribute("name"), ["/", "*", "-", "_", ":", " "]).lower()

            if not label_txt:
                continue
            elif "address" in label_txt:
                label_txt += "street"
            elif "post" in label_txt:
                label_txt += "zip"
            for key in json_userInfo.keys():
                if nlp.remove_elements(key, [" "]) in label_txt:
                    elem.click()
                    elem.send_keys(json_userInfo[key])
                    break
        return True

    def click_to_order(self, driver):
        logger = logging.getLogger('shop_crawler')
        dest = []

        while True:
            dest = find_buttons_or_links(driver, ["confirm*.*order", "place*.*order", "to payment", "to paypal"])

            if dest:
                break
            continue_btns = find_buttons_or_links(driver, ["continue"], ["login"])
            if not continue_btns:
                bill_btns = find_buttons_or_links(driver, ["bill"])
                if not bill_btns:
                    logger.debug('Step over error')
                    return False
                bill_btns[len(continue_btns) - 1].click()
            else:
                continue_btns[len(continue_btns) - 1].click()
            time.sleep(2)
        dest[0].click()
        return True

    def get_elem_attribute(self, elem, attrs):
        for item in attrs:
            if elem.get_attribute(item):
                return elem.get_attribute(item)
        return None

    def filter_page(self, driver, state, content):
        if self.find_pwd_in_checkout(driver):
            if not self.find_auth_pass_elements(driver):
                return False
        return True

    def process_page(self, driver, state, context):
        auth_pass = self.find_auth_pass_elements(driver)

        #the case if authentication is requiring, pass authentication by creating an account as guest...
        if auth_pass:
            #create an account as guest....
            if not click_first(driver, auth_pass):
                return state
            account_btn = find_buttons_or_links(driver, ["button*.*account", "account*.*button"])
            if account_btn:
                if click_first(driver, account_btn):
                    time.sleep(3)

        #the case if authentication is not requiring....
        dest = find_buttons_or_links(driver, ["confirm*.*order", "place*.*order", "to payment", "to paypal"])

        if not dest:
            #Fill checkout fields step by step.....
            if not self.fill_billing_address(driver, context):
                return state
            if not self.click_to_order(driver):
                return state
        else:
            #Fill all fields of checkout page in one page....
            self.fill_billing_address(driver, context)


    
class GoogleForProductPage(IStepActor):
    def get_states(self):
        return [States.new, States.shop, States.product_page]
        
    def search(self, driver, google_query):
        driver.get('http://google.com')
        search_input = driver.find_element_by_css_selector('input.gsfi')
        search_input.clear()
        search_input.send_keys(google_query)
        search_input.send_keys(Keys.ENTER)
        
        links = driver.find_elements_by_css_selector('div.g .rc .r a[href]')
        if len(links) > 0:
            return links[0].get_attribute("href")
        else:
            return None
    
    def search_for_product_link(self, driver, domain):
        queries = ['add to cart']

        # Open a new tab
        new_tab(driver)
        driver.get('https://google.com')
        for query in queries:
            google_query = 'site:{} {}'.format(domain, query)
            link = self.search(driver, google_query)
            if link:
                break
        
        # Close new tab
        close_tab(driver)
        
        return link
    
    def process_page(self, driver, state, context):
        link = self.search_for_product_link(driver, context.domain)
        
        if link:
            url = ShopCrawler.normalize_url(link)
            driver.get(url)
            return States.product_page
        
        return state
    
       
def add_crawler_extensions(crawler):
    crawler.add_handler(AddToCart(), 4)
    crawler.add_handler(GoogleForProductPage(), 3)
    crawler.add_handler(ToProductPageLink(), 2)
    crawler.add_handler(ToShopLink(), 1)
    crawler.add_handler(ToCheckout(), 3)
    crawler.add_handler(ToCartLink(), 2)
    