from shop_crawler import *
from selenium_helper import *
import nlp

from common_heuristics import *

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import ElementNotVisibleException
import sys
import re
import traceback
import time
import calendar

def find_in_elems(elements, contains=None, not_contains=None, check_or_radio=False):
    result = []
    for elem in elements:
        if not can_click(elem) and not check_or_radio:
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


def find_radio_or_checkout_button(driver,
                                  contains=None,
                                  not_contains=None):
    radiobtns = driver.find_elements_by_css_selector("input[type='radio']")
    checkbtns = driver.find_elements_by_css_selector("input[type='checkbox']")

    return find_in_elems((radiobtns + checkbtns), contains, not_contains, True)


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
        return element.get_attribute("outerHTML")
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
        logger.debug('clicking element: {}'.format(to_string(element)))
        clicked = process(element)
        logger.debug('result: {}'.format(clicked))
                     
        if clicked:
            return True

        if on_error and on_error(driver):
            if process(element):
                return True

    return False


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


def try_handle_popups(driver):
    btns = find_buttons_or_links(
        driver,
        ["i .*over", "i .*age", ".* agree .*"],
        [' .*not.*', " .*under.*"]
    )
    return click_first(driver, btns)


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
        words = nlp.tokenize(text)
        if 'buy' in words:
            return len(words) <= 2
        
        return True
        
    def find_to_cart_elements(self, driver):
        btns = find_buttons_or_links(driver, ["add to cart",
                                              "add to bag",
                                              "buy"], ['where'])
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

        if click_first(driver, btns):
            time.sleep(30)
            if not is_empty_cart(driver):
                return States.cart_page
        
        return state


class ToCheckout(IStepActor):
    def find_checkout_elements(self, driver):
        return find_buttons_or_links(driver, ["checkout", "check out"])

    def get_states(self):
        return [States.product_in_cart, States.cart_page]

    def process_page(self, driver, state, context):
        btns = self.find_checkout_elements(driver)

        if click_first(driver, btns):
            time.sleep(10)
            if not is_empty_cart(driver):
                return States.checkout_page
        
        return state


class PaymentFields(IStepActor):
    def get_states(self):
        return [States.checkout_page]

    def find_pwd_in_checkout(self, driver):
        pwd_inputs = driver.find_elements_by_css_selector("input[type='password']")

        return pwd_inputs

    def find_auth_pass_elements(self, driver):
        return find_radio_or_checkout_button(driver, ["guest", "create*.*later"])

    def get_label_text_with_attribute(self, driver, elem):
        label_txt = ""
        element_attribute = nlp.get_element_attribute(elem)

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
                        context.user_info.state,
                        context.user_info.country,
                        context.payment_info.card_type,
                        str(context.payment_info.expire_date_year),
                        calendar.month_abbr[context.payment_info.expire_date_month],
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
            order = find_buttons_or_links(
                driver,
                ["confirm*.*order", "place*.*order", "pay*.*order"]
            )
            agree_btns = find_radio_or_checkout_button(
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

        order_attribute = nlp.get_element_attribute(order[0])
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

    def filter_page(self, driver, state, content):
        password_fields = self.find_pwd_in_checkout(driver)
        logger = logging.getLogger("shop_crawler")
        if password_fields:
            if password_fields[0].is_displayed():
                if not self.find_auth_pass_elements(driver):
                    logger.debug("We can't use this url! Login password required!")
                    return False
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


    
class GoogleForProductPage(IStepActor):
    def get_states(self):
        return [States.new, States.shop, States.product_page]
        
    def search(self, driver, google_query):
        driver.get('http://google.com')
        search_input = driver.find_element_by_css_selector('input.gsfi')
        search_input.clear()
        search_input.send_keys(google_query)
        search_input.send_keys(Keys.ENTER)
        
        # Check if no exact results
        statuses = driver.find_elements_by_css_selector('div.obp div.med')
        for status in statuses:
            if re.search(google_query, status.text):
                return None
        
        links = driver.find_elements_by_css_selector('div.g .rc .r a[href]')
        if len(links) > 0:
            return links[0].get_attribute("href")
        else:
            return None

    def search_for_product_link(self, driver, domain):
        queries = ['"add to cart"']

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
    crawler.add_handler(PaymentFields(), 2)
