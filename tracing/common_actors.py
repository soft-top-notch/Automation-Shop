from shop_tracer import *
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
from selenium.common.exceptions import ElementNotVisibleException, TimeoutException, StaleElementReferenceException


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

            url = ShopTracer.normalize_url(link)
            driver.get(url)
            time.sleep(3)
            
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
            time.sleep(3)
            return States.product_in_cart
        else:
            return state


class ToShopLink(IStepActor):
    def get_states(self):
        return [States.new]

    def find_to_shop_elements(self, driver):
        return find_buttons_or_links(driver, ["shop", "store", "products"], ["shops", "stores", "shopping", "condition", "policy"])

    def process_page(self, driver, state, context):
        elements = self.find_to_shop_elements(driver)
        if click_first(driver, elements, try_handle_popups):
            return States.shop
        else:
            return state


class ClosePopups(IStepActor):
    def get_states(self):
        return [States.new]
    
    def process_page(self, driver, state, context):
        if try_handle_popups(driver):
            logger = logging.getLogger("shop_tracer")
            logger.info("Popup closed")

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
                time.sleep(3)
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
        not_contains = ['continue shopping', 'return']
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
            time.sleep(3)
            close_alert_if_appeared(driver)
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

    def find_auth_pass_buttons(self, driver):
        radio_checkbox_btns = find_radio_or_checkbox_buttons(
            driver,
            ["guest", "create*.*later", "copy*.*ship", "copy*.*bill", "skip*.*login", "register"]
        )
        if radio_checkbox_btns:
            return radio_checkbox_btns
        else:
            text_element = find_text_element(driver, ["guest", "(no|without|free|create).*account", "account.*.(no|without|free)"])
            if text_element:
                pass_button = []

                for button in find_buttons_or_links(driver, ["continue", "checkout", "check out" "go", "create.*.account", "new.*.customer"], ["login"]):
                    if button.get_attribute('href') == normalize_url(get_url(driver)):
                        continue
                    pass_button.append(button)

                return pass_button
        return None

    def new_account_field_exist(self, driver, create_new_field):
        text_element = find_text_element(driver, ["(no|without|free|create).*account", "guest", "account.*.(no|without|free)"])

        if not text_element:
            return False

        password_field = text_element.find_element_by_xpath("../..")
        password_field = password_field.find_element_by_css_selector("input[type='password']")

        if password_field and password_field == create_new_field:
            return True
        return False

    def check_login(self, driver, context):
        password_fields = self.find_pwd_in_checkout(driver)
        logger = logging.getLogger("shop_tracer")

        if password_fields:
            if len(password_fields) >= 2:
                return True
            if password_fields[0].is_displayed():
                if not self.find_auth_pass_buttons(driver):
                    if not self.new_account_field_exist(driver, password_fields[0]):
                        logger.debug("We can't use this url! Login password required!")
                        return False
        return True

    def filter_page(self, driver, state, context):
        return_flag = True

        if not self.check_login(driver, context):
            return_flag = False
        return return_flag

    def get_label_text_with_attribute(self, driver, elem):
        label_txt = ""
        element_attribute = get_element_attribute(elem)

        try:
            if element_attribute:
                if element_attribute[0] == "id":
                    label = driver.find_elements_by_css_selector("label[for='%s']" % element_attribute[1])
                    if label:
                        label_txt = nlp.remove_letters(label[0].get_attribute("innerHTML").strip(), ["/", "*", "-", "_", ":", " "]).lower()
                        return label_txt

            label_txt = nlp.remove_letters(
                    elem.get_attribute("outerHTML").strip(),
                    ["*", "-", "_", ":", " "]
            ).lower()
        except:
            label_txt = ""
            pass

        return label_txt

    def find_select_element(self, driver, contain, consider_contain=None):
        selects = driver.find_elements_by_css_selector("select")
        selected_sels = []
        pass_once = False
        content = contain
        result = None

        if consider_contain:
            if content == consider_contain[0]:
                content = consider_contain[1]
                pass_once = True

        for sel in selects:
            label_text = self.get_label_text_with_attribute(driver, sel)
            not_contains = []
            if content == "state":
                not_contains = ["unitedstate"]
            elif content == "ex":
                not_contains = ["state", "country"]
            if nlp.check_text(label_text, [content], not_contains):
                if pass_once:
                    pass_once = False
                    continue
                selected_sels.append(sel)
        if len(selected_sels) == 1:
            result = selected_sels[0]
        elif len(selected_sels) > 1:
            result = None
            for sel in selected_sels:
                if not sel.is_displayed():
                    continue
                result = sel
                break
        return result

    def process_select_option(self, driver, contains, context):
        result_cnt = 0
        for item in contains:
            sel = self.find_select_element(driver, item, ['ex1', 'ex'])
            if not sel:
                continue
            for option in sel.find_elements_by_css_selector("option"):
                text = option.text + " " + option.get_attribute("innerHTML").strip()
                if nlp.check_text(text, [
                        nlp.normalize_text(get_name_of_state(context.user_info.state)),
                        "united states",
                        nlp.normalize_text(context.payment_info.card_type),
                        "(\d\d|^){}$".format(context.payment_info.expire_date_year),
                        nlp.normalize_text(calendar.month_abbr[int(context.payment_info.expire_date_month)]),
                        context.payment_info.expire_date_month,
                        "^{}$".format(nlp.normalize_text(context.user_info.state))
                    ]):
                    try:
                        time.sleep(2)
                        option.click() # select() in earlier versions of webdriver
                        time.sleep(2)
                        result_cnt += 1
                        break
                    except:
                        return False
        return result_cnt

    def input_fields_in_checkout(self,
                                 driver,
                                 context,
                                 select_contains,
                                 extra_contains,
                                 is_userInfo=True,
                                 not_extra_contains=None,
                                 not_contains=None
                                 ):

        logger = logging.getLogger('shop_tracer')

        success_flag = False
        inputed_fields_cnt = 0
        selected_count = self.process_select_option(driver, select_contains, context)
        if not selected_count:
            logger.debug("Not found select options!")

        input_texts = driver.find_elements_by_css_selector("input")
        input_texts += driver.find_elements_by_css_selector("textarea")
        time.sleep(1)

        if is_userInfo:
            json_Info = context.user_info.get_json_userinfo()
        else:
            json_Info = context.payment_info.get_json_paymentinfo()

        for elem in input_texts:
            label_text = ""
            try:
                if elem.is_displayed() and not nlp.check_text(elem.get_attribute("type"), ["button", "submit", "radio", "checkbox", "image"]):
                    label_text = self.get_label_text_with_attribute(driver, elem)

                if not label_text:
                    continue

                for conItem in extra_contains:
                    not_text_contains = not_extra_contains
                    if conItem[0] == "comp":
                        not_text_contains = not_text_contains + ["complete"]
                    if nlp.check_text(label_text, conItem[0].split(","), not_text_contains):
                        label_text += " " + conItem[1]
                        break
                for key in json_Info.keys():
                    if nlp.check_text(label_text.replace("name=", " ").replace("type=", " "), [nlp.remove_letters(key, [" "])], not_contains):
                        try:
                            elem.click()
                            elem.clear()
                            if key == "phone":
                                elem.send_keys(nlp.remove_letters(json_Info[key], ["(", ")", "-"]))
                            else:
                                elem.send_keys(json_Info[key])
                            success_flag = True
                            inputed_fields_cnt += 1
                        except:
                            pass
                        break
            except:
                continue
        if success_flag:
            if (inputed_fields_cnt + selected_count) < (len(json_Info.keys()) - 4):
                success_flag = False
        time.sleep(1)
        return success_flag

    def fill_billing_address(self, driver, context):
        select_contains = ["country", "state", "zone"]
        not_extra_contains = ["email", "address2", "firstname", "lastname", "street"]
        extra_contains = [
            ["fname,namefirst", "firstname"],
            ["lname,namelast", "lastname"],
            ["comp", "company"],
            ["address", "street"], # First item is a sub-string to check in text, Second item is a string to add in text
            ["post", "zip"]
        ]
        not_contains = [
            "street(2|3)", "phone(_|-|)(\w|\w\w|\w\w\w|)(2|3)"
        ]

        return self.input_fields_in_checkout(
            driver,
            context,
            select_contains,
            extra_contains,
            True,
            not_extra_contains,
            not_contains
        )

    def fill_payment_info(self, driver, context):
        select_contains = ["card", "month", "year", "ex", "ex1"]
        not_extra_contains = ["company"]
        extra_contains = [
            ["owner", "name"],
            ["cc.*n", "number"],
            ["comp", "company"],
            ["mm(|\w+)yy,(\w\w|\d\d)/(\w\w|\d\d)", "expdate"],
            ["c\w+(num|num\w+)", "number"],
            ["exp", "expdate"],
            ["verif.*,sec.*,cv,ccc,cc\wc,csc", "cvc"]
        ]
        not_contains = [
            "first", "last", "phone", "company",
            "fname", "lname", "user", "email",
            "address", "code", "street", "city", "post"
        ]

        return self.input_fields_in_checkout(
            driver,
            context,
            select_contains,
            extra_contains,
            False,
            not_extra_contains = not_extra_contains,
            not_contains=not_contains
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

    def check_iframe_and_fill(self, driver, context):
        iframes = driver.find_elements_by_css_selector("iframe")
        enabled_iframes = []
        success_flag = False

        for iframe in iframes:
            if iframe.is_displayed():
                enabled_iframes.append(iframe)

        if not enabled_iframes:
            return False

        for iframe in enabled_iframes:
            driver.switch_to_frame(iframe)
            if self.fill_payment_info(driver, context):
                success_flag = True
            driver.switch_to_default_content()

        return success_flag

    def check_error(self, driver, context):
        '''Check error elements after clicking order button'''
        logger = logging.getLogger('shop_tracer')
        error_result = []
        error_elements = find_error_elements(driver, ["error", "err", "alert", "advice", "fail", "invalid"], ["override"])
        time.sleep(2)

        required_fields = driver.find_elements_by_css_selector("input")
        required_fields += driver.find_elements_by_css_selector("select")

        if error_elements:
            while True:
                try:
                    for element in error_elements:
                        text = nlp.remove_letters(element.get_attribute("innerHTML").strip(), ["/", "*", "-", "_", ":", " "]).lower()
                        for field in required_fields:
                            if field.is_displayed():
                                label_text = self.get_label_text_with_attribute(driver, field)
                                if label_text and nlp.check_text(text, [label_text]):
                                    error_result.append(label_text + " field required")
                        if not error_result:
                            contain = ["company", "first", "last", "address",
                                      "street", "city", "state", "zip", "phone",
                                      "email", "town", "cvc", "ccv", "credit"]
                            for item in contain:
                                not_contains = []
                                contains = [item]
                                if item == "address":
                                    not_contains = ["phone", "email"]
                                elif item == "state":
                                    contains.append("city")
                                    not_contains = ["\d+"]
                                elif item == "credit":
                                    contains.append("card")
                                if nlp.check_text(text, contains, not_contains):
                                    if item == "credit":
                                        item += " card"
                                    elif item == "first" or item == "last":
                                        item += " name"
                                    error_result.append(item + " field not correct or required")
                    break
                except StaleElementReferenceException:
                    error_elements = find_error_elements(driver, ["error", "err", "alert", "advice", "fail"], ["override"])
                    time.sleep(2)
                    pass

            if not error_result:
                logger.debug("Input data not correct")
            else:
                logger.debug(error_result)
            return False
        return True

    def click_to_order(self, driver, context):
        logger = logging.getLogger('shop_tracer')

        return_flag = True
        is_paymentinfo = False
        payment_url = None
        try_cnt = 0
        while True:
            is_userinfo = True
            if try_cnt >= 6:
                logger.debug("Error found in filling all fields")
                return_flag = False
                break
            if not self.fill_billing_address(driver, context):
                print("Billing information is already inputed or something wrong!")
                is_userinfo = False

            if not is_paymentinfo:
                if self.fill_payment_info(driver, context):
                    is_paymentinfo = True
                else:
                    if self.check_iframe_and_fill(driver, context):
                        is_paymentinfo = True
            order = find_buttons(
                driver,
                ["order", "pay", "checkout", "payment", "create*.*account"],
                ["add", "modify", "coupon", "express", "continu", "border", "proceed"]
            )

            agree_btns = find_radio_or_checkbox_buttons(
                driver,
                ["agree", "terms", "paypal", "same", "copy", "remember", "keep", "credit"],
                ["express"]
            )

            if agree_btns:
                for elem in agree_btns:
                    if elem.is_displayed() and not elem.is_selected():
                        try:
                            elem.send_keys(selenium.webdriver.common.keys.Keys.SPACE)
                            time.sleep(0.5)
                        except ElementNotVisibleException:
                            pass

            div_btns = find_elements_with_attribute(driver, "div", "class", "shipping_method")

            if div_btns:
                div_btns[0].click()
                time.sleep(1)

            if order:
                break

            continue_btns = []
            for btn in find_buttons_or_links(driver, ["continu", "next", "proceed"], ["login", "cancel"]):
                if btn.get_attribute('href') == normalize_url(get_url(driver)):
                    continue
                continue_btns.append(btn)
            flag = False

            if continue_btns:
                try:
                    continue_btns[len(continue_btns) - 1].click()
                except:
                    flag = True
                    pass
            if flag or not continue_btns:
                forward_btns = []
                for btn in find_buttons_or_links(driver, ["bill", "proceed"], ["modify", "express", "cancel"]):
                    if btn.get_attribute('href') == normalize_url(get_url(driver)):
                        continue
                    forward_btns.append(btn)
                if not forward_btns:
                    if is_userinfo or is_paymentinfo:
                        logging.debug("Proceed button not found!")
                    return_flag = False
                    break
                forward_btns[len(forward_btns) - 1].click()
            time.sleep(7)
            if not self.check_error(driver, context):
                logging.debug("Error found in checking!")
                return_flag = False
                break
            try_cnt += 1

        if not return_flag:
            return False

        if order[0].get_attribute('href'):
            payment_url = order[0].get_attribute('href')

        '''paying or clicking place order for paying...'''
        order[0].click()
        time.sleep(5)
        if not self.check_error(driver, context):
            return False

        '''paying if payment info is not inputed'''
        if payment_url:
            driver.get(payment_url)

        if not is_paymentinfo:
            for _ in (0, 2):
                pay_button = []
                for button in find_buttons_or_links(driver,["pay", "order"], ["border"]):
                    if button.get_attribute('href') == normalize_url(get_url(driver)):
                        continue
                    pay_button.append(button)
                if pay_button:
                    if not self.fill_payment_info(driver, context) and not self.check_iframe_and_fill(driver, context):
                        logging.debug("Payment information is already inputed or payment field not exist!")
                    else:
                        is_paymentinfo = True
                    if not self.click_one_element(pay_button):
                        logging.debug("Pay or order button error!")
                    else:
                        time.sleep(3)
                else:
                    if not is_paymentinfo:
                        logging.debug("Payment information can not be inputed!")
                        return False
                    break

        return_flag = self.check_error(driver, context)
        if return_flag:
            logging.debug("Successed!")

        return return_flag

    def process_page(self, driver, state, context):
        #the case if authentication is requiring, pass authentication by creating an account as guest...
        time.sleep(4)
        auth_pass = self.find_auth_pass_buttons(driver)
        if auth_pass:
            #create an account as guest....
            if not click_first(driver, auth_pass):
                return state
            time.sleep(2)
            account_btn = []
            for button in find_buttons_or_links(driver, ["continue"]):
                if (button.get_attribute('href') == normalize_url(get_url(driver))) or \
                    (nlp.check_text(button.get_attribute("outerHTML"), ["login", "sign"])):
                    continue
                account_btn.append(button)
            if account_btn:
                if click_first(driver, account_btn):
                    time.sleep(2)

        #the case if authentication is not requiring....
        filling_result = self.click_to_order(driver, context)
        if not filling_result:
            return state

        return States.purchased

    
class SearchForProductPage(IStepActor):

    def get_states(self):
        return [States.new, States.shop]
        
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
                        logger = logging.getLogger('shop_tracer')
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


def add_tracer_extensions(tracer):
    tracer.add_handler(ClosePopups(), 5)
    
    tracer.add_handler(AddToCart(), 4)
    tracer.add_handler(SearchForProductPage(), 1)
    tracer.add_handler(ToProductPageLink(), 3)
    tracer.add_handler(ToShopLink(), 2)

    tracer.add_handler(ToCheckout(), 3)
    tracer.add_handler(ToCartLink(), 2)
    tracer.add_handler(PaymentFields(), 2)
