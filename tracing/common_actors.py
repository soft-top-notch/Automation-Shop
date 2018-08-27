from shop_tracer import *
from selenium_helper import *
from common_heuristics import *

import nlp
import random
import sys
import traceback
import time
import calendar
import csv

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import ElementNotVisibleException, TimeoutException, StaleElementReferenceException, NoSuchElementException


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
        not_contains = ['continue shopping', 'return', 'guideline', 'login', 'log in', 'sign in', 'view cart', 'logo']
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

    def find_guess_continue_button(self, driver):
        text_element = find_text_element(driver, ["guest", "(no|without|free|create).*account", "account.*.(no|without|free)"])
        if text_element:
            pass_button = []


            for button in find_buttons_or_links(
                driver,
                ["continue", "checkout", "check out",
                "(\s|^)go(\s|$)","new.*.customer"],
                ["login", "continue shopping", "cart", "logo", "return", "signin"]
            ):
                if button.get_attribute("href") and button.get_attribute("href") in normalize_url(get_url(driver)):
                    continue
                pass_button.append(button)

            if not pass_button:
                for button in find_buttons_or_links(
                    driver,
                    ["forgot.*.password"], ["cart", "logo", "return", "continue shopping"]
                ):
                    if button.get_attribute('href') == normalize_url(get_url(driver)):
                        continue
                    pass_button.append(button)
            return pass_button
        return None

    def find_radio_continue_buttons(self, driver):
        radio_checkbox_btns = find_radio_or_checkbox_buttons(
            driver,
            ["guest", "create*.*later", "copy*.*ship", "copy*.*bill", "skip*.*login", "register"]
        )

        if radio_checkbox_btns:
            return radio_checkbox_btns

        return None

    def new_account_field_exist(self, driver, create_new_field):
        text_element = find_text_element(driver, ["guest", "(no|without|free|create).*account", "account.*.(no|without|free)"], ["login","signin","sign in"])

        if not text_element:
            return False

        password_field = text_element.find_element_by_xpath("../..")
        try:
            password_field = password_field.find_element_by_css_selector("input[type='password']")
        except NoSuchElementException:
            return False

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
                if not self.find_radio_continue_buttons(driver) and not self.find_guess_continue_button(driver):
                    if not self.new_account_field_exist(driver, password_fields[0]):
                        logger.debug("We can't use this url! Login password required!")
                        return False
        return True

    def filter_page(self, driver, state, context):
        return_flag = True

        if not self.check_login(driver, context):
            return_flag = False
        return return_flag

    def find_select_element(self, driver, contain, consider_contain=None):
        selects = driver.find_elements_by_css_selector("select")
        selected_sels = []
        pass_once = False
        content = contain

        if consider_contain:
            if content == consider_contain[0]:
                content = consider_contain[1]
                pass_once = True

        for sel in selects:
            try:
                label_text = get_label_text_with_attribute(driver, sel)
            except:
                continue
            not_contains = []
            if content == "state":
                not_contains = ["unitedstate"]
            elif content == "ex":
                not_contains = ["state", "country", "express"]
            if nlp.check_text(label_text, [content], not_contains):
                if pass_once:
                    pass_once = False
                    continue
                selected_sels.append(sel)
        return selected_sels

    def process_select_option(self, driver, contains, context):
        result_cnt = 0
        for item in contains:
            selects = self.find_select_element(driver, item, ['ex1', 'ex'])
            if not selects:
                continue
            for sel in selects:
                try:
                    flag = False
                    for option in sel.find_elements_by_css_selector("option"):
                        text = option.text + " " + option.get_attribute("innerHTML").strip()
                        ctns  = []

                        if item == "country":
                            ctns = ["united states"]
                        elif item == "day":
                            ctns = ["27"]
                        elif item == "state":
                            ctns = [
                                nlp.normalize_text(get_name_of_state(context.user_info.state)),
                                "(^|\s){}$".format(nlp.normalize_text(context.user_info.state))
                            ]
                        else:
                            ctns = [
                                nlp.normalize_text(context.payment_info.card_type),
                                "(\d\d|^){}$".format(context.payment_info.expire_date_year),
                                "(^|-|_|\s|\d){}".format(nlp.normalize_text(calendar.month_abbr[int(context.payment_info.expire_date_month)])),
                                context.payment_info.expire_date_month
                            ]
                        if nlp.check_text(text, ctns):
                            try:
                                time.sleep(2)
                                option.click() # select() in earlier versions of webdriver
                                time.sleep(2)
                                result_cnt += 1
                                flag = True
                                break
                            except:
                                break
                    if flag:
                        break
                except:
                    continue
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

        inputed_fields = []
        cycle_count = 0
        confirm_pwd = False
        index = 0

        selected_count = self.process_select_option(driver, select_contains, context)
        if not selected_count:
            logger.debug("Not found select options!")

        input_texts = driver.find_elements_by_css_selector("input")
        input_texts += driver.find_elements_by_css_selector("textarea")
        time.sleep(1)

        if is_userInfo:
            json_Info = context.user_info.get_json_userinfo()
            confirm_pwd = False
        else:
            json_Info = context.payment_info.get_json_paymentinfo()
            confirm_pwd = True

        while index < len(input_texts):
            label_text = ""
            try:
                if input_texts[index].is_displayed() and not nlp.check_text(input_texts[index].get_attribute("type"), ["button", "submit", "radio", "checkbox", "image"]):
                    label_text = get_label_text_with_attribute(driver, input_texts[index])

                if not label_text:
                    index += 1
                    continue
            except:
                if cycle_count >= 2:
                    cycle_count = 0
                    index += 1
                    continue
                time.sleep(2)
                input_texts = driver.find_elements_by_css_selector("input")
                input_texts += driver.find_elements_by_css_selector("textarea")
                cycle_count += 1
                continue

            for conItem in extra_contains:
                not_text_contains = not_extra_contains
                if conItem[0] == "comp":
                    not_text_contains = not_text_contains + ["complete"]
                if nlp.check_text(label_text, conItem[0].split(","), not_text_contains):
                    if conItem[1] == "number" and nlp.check_text(label_text, ["verif.*"]):
                        conItem[1] = "cvc"
                    label_text += " " + conItem[1]
                    break
            for key in json_Info.keys():
                if key in inputed_fields:
                    continue
                _not_contains = not_contains
                if key == "type":
                    _not_contains = _not_contains + ["typehere"]
                elif key == "city":
                    _not_contains = _not_contains + ["opacity"]
                elif key == "number":
                    _not_contains = _not_contains + ["verif.*", "number\d"]
                if nlp.check_text(label_text.replace("name=", " ").replace("type=", " "), [nlp.remove_letters(key, [" "])], _not_contains):
                    try:
                        input_texts[index].click()
                        input_texts[index].clear()
                    except:
                        driver.execute_script("arguments[0].click();",input_texts[index])
                        pass
                    try:
                        if key == "phone":
                            input_texts[index].send_keys(nlp.remove_letters(json_Info[key], ["(", ")", "-"]))
                        elif key == "country":
                            input_texts[index].send_keys("united states")
                        elif key == "state":
                            input_texts[index].send_keys(nlp.normalize_text(get_name_of_state(context.user_info.state)))
                        elif key == "number":
                            input_texts[index].send_keys(json_Info[key])
                            time.sleep(5)
                        else:
                            input_texts[index].send_keys(json_Info[key])
                        time.sleep(1)
                    except:
                        break

                    inputed_fields.append(key)
                    if (key == "password" and not confirm_pwd) or (key == "email"):
                        confirm_pwd = True
                        inputed_fields.pop()
                    break
            index += 1

        time.sleep(1)

        if len(inputed_fields) == 1 and inputed_fields[0] == "zip":
            return len(inputed_fields) - 1
        return len(inputed_fields)

    def fill_billing_address(self, driver, context):
        select_contains = ["country", "state", "zone"]
        not_extra_contains = ["email", "address2", "firstname", "lastname", "street", "city", "company", "country", "state", "search"]
        extra_contains = [
            ["(^|_|-|\s)fname,namefirst,username,first_name", "firstname"],
            ["(^|_|-|\s)lname,namelast,last_name", "lastname"],
            ["comp", "company"],
            ["post", "zip"],
            ["address", "street"] # First item is a sub-string to check in text, Second item is a string to add in text
        ]
        not_contains = [
            "street(\s|)(line|)(2|3)", "phone(_|-|)(\w|\w\w|\w\w\w|)(2|3)"
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
        select_contains = ["card", "month", "year", "day", "ex", "ex1"]
        not_extra_contains = ["company"]
        extra_contains = [
            ["owner", "name"],
            ["cc.*n,c\w+(num|num\w+),cardinput", "number"],
            ["comp", "company"],
            ["birth,(\w\w|\d\d)/(\w\w|\d\d)/(\w\w|\d\d|\d\d\d\d|\w\w\w\w)", "birthdate"],
            ["mm(|\w+)yy,(\w\w|\d\d)/(\w\w|\d\d)", "expdate"],
            ["exp", "expdate"],
            ["verif.*,sec.*,cv,cc(\w|)c,csc,card(\w+|\s|)code", "cvc"],
            ["post", "zip"]
        ]
        not_contains = [
            "first", "last", "phone", "company",
            "fname", "lname", "user", "email",
            "address", "street", "city",
            "gift", "vat", "filter"
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

    def get_continue_button(self, driver, contains, not_contains=None):
        continue_btns = []

        for btn in find_buttons_or_links(driver, contains, not_contains):
            if btn.get_attribute('href') == normalize_url(get_url(driver)):
                continue
            continue_btns.append(btn)

        return continue_btns

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

    def click_continue_in_iframe(self, driver):
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
            self.check_agree_and_click(driver)
            elements = self.get_continue_button(driver,["continu", "(\s|^)pay", "submit"])
            if self.click_one_element(elements):
                success_flag = True
            driver.switch_to_default_content()

        return success_flag

    def check_agree_and_click(self, driver):
        '''Clicking radio and checkboxes for proceed'''
        agree_btns = find_radio_or_checkbox_buttons(
            driver,
            ["agree", "terms","same", "copy",
            "different", "register", "remember", "keep", "credit", "paypal",
            "stripe", "mr", "standard", "free", "deliver",
            "billing_to_show", "ground", "idt","gender"],
            ["express"]
        )
        cycle_count = 0
        index = 0

        if agree_btns:
            while index < len(agree_btns):
                try:
                    check_exception = agree_btns[index].get_attribute("outerHTML")
                except:
                    if cycle_count >= 2:
                        cycle_count = 0
                        index += 1
                        continue
                    agree_btns = find_radio_or_checkbox_buttons(
                        driver,
                        ["agree", "terms", "paypal", "same", "copy",
                        "different", "remember", "keep", "credit",
                        "stripe", "register", "mr", "standard", "free",
                        "billing_to_show", "ground", "idt", "gender"],
                        ["express"]
                    )
                    cycle_count += 1
                    continue
                if nlp.check_text(agree_btns[index].get_attribute("outerHTML"), ["differ", "register"], ["same"]):
                    if not nlp.check_text(agree_btns[index].get_attribute("outerHTML"), ["radio"]):
                        if agree_btns[index].is_displayed() and agree_btns[index].is_selected():
                            agree_btns[index].send_keys(selenium.webdriver.common.keys.Keys.SPACE)
                            time.sleep(0.5)
                else:
                    if agree_btns[index].is_enabled() and not agree_btns[index].is_selected():
                        try:
                            agree_btns[index].send_keys(selenium.webdriver.common.keys.Keys.SPACE)
                        except ElementNotVisibleException:
                            driver.execute_script("arguments[0].click();", agree_btns[index])
                            pass
                        time.sleep(1)
                index += 1

    def check_alert_text(self, driver):
        try:
            alert = driver.switch_to.alert

            if nlp.check_text(alert.text, ["decline", "duplicate", "merchant", "transaction"]):
                alert.accept()
                return True
        except:
            return False

    def check_error(self, driver, context):
        '''Check error elements after clicking order button'''
        logger = logging.getLogger('shop_tracer')
        error_result = []
        try:
            error_elements = find_error_elements(driver, ["error", "err", "alert", "advice", "fail", "invalid"], ["override"])
        except:
            if self.check_alert_text(driver):
                return 2
            return 0
        time.sleep(2)

        required_fields = driver.find_elements_by_css_selector("input")
        required_fields += driver.find_elements_by_css_selector("select")

        if error_elements:
            if len(error_elements) == 1 and nlp.check_text(
                error_elements[0].get_attribute("outerHTML"),
                ["credit", "merchant", "payment", "security","transaction", "decline", "permit"],
                ["find", "require"]):
                return 2
            elif len(error_elements) == 2 and nlp.check_text(error_elements[1].get_attribute("outerHTML"), ["password"]):
                return 1
            while True:
                try:
                    for element in error_elements:
                        text = nlp.remove_letters(element.get_attribute("innerHTML").strip(), ["/", "*", "-", "_", ":", " "]).lower()
                        for field in required_fields:
                            if field.is_displayed():
                                label_text = get_label_text_with_attribute(driver, field)
                                if label_text and nlp.check_text(text, [label_text]):
                                    error_result.append(label_text + " field required")
                        if not error_result:
                            contain = ["password", "company", "first", "last", "address",
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
            for elem in error_result:
                if "password" in elem:
                    return 1
            return 0
        return 1

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

            self.check_agree_and_click(driver)

            if not self.fill_billing_address(driver, context):
                print("Billing information is already inputed or something wrong!")
                is_userinfo = False
            else:
                context.log_step("Fill user information fields")
                time.sleep(2)

            div_btns = find_elements_with_attribute(driver, "div", "class", "shipping_method")

            if div_btns:
                div_btns[0].click()
                time.sleep(1)

            if not is_paymentinfo:
                if self.fill_payment_info(driver, context):
                    is_paymentinfo = True
                    context.log_step("Fill payment info fields")
                else:
                    if self.check_iframe_and_fill(driver, context):
                        is_paymentinfo = True
                        context.log_step("Fill payment info fields")
            order = []

            for button in find_buttons(
                            driver,
                            ["order", "pay", "checkout", "payment", "buy"],
                            ["add", "modify", "coupon", "express",
                            "continu", "border", "proceed", "review",
                            "guest", "complete", "detail", "\.paypal\.",
                            "currency", "histor", "amazon"]
                        ):
                if button.get_attribute("href") == get_url(driver):
                    continue
                order.append(button)

            if order:
                break

            continue_btns = self.get_continue_button(driver,
                ["continu", "next", "proceed", "complete"],
                ["login", "cancel"]
            )
            flag = False

            if continue_btns:
                try:
                    continue_btns[len(continue_btns) - 1].click()
                except:
                    flag = True
                    pass
            if flag or not continue_btns:
                continue_btns = []
                for btn in find_buttons_or_links(driver, ["bill", "proceed", "submit", "create*.*account", "add", "save"], ["modify", "express", "cancel"]):
                    if btn.get_attribute('href') == normalize_url(get_url(driver)):
                        continue
                    continue_btns.append(btn)
                if not continue_btns:
                    if is_userinfo or is_paymentinfo:
                        logging.debug("Proceed button not found!")
                    return_flag = False
                    break
                try:
                    continue_btns[len(continue_btns) - 1].click()
                except:
                    driver.execute_script("arguments[0].click();",continue_btns[len(continue_btns) - 1])
                    pass
            time.sleep(context.delaying_time)
            checked_error = self.check_error(driver, context)

            if not checked_error:
                logging.debug("Error found in checking!")
                return_flag = False
                break
            elif checked_error == 1:
                if self.check_alert_text(driver):
                    return True
                purchase_text = get_page_text(driver)
                if nlp.check_text(purchase_text, ["being process"]):
                    time.sleep(2)
                elif nlp.check_text(purchase_text, ["credit card to complete your purchase", "secure payment page"]):
                    return True
            elif checked_error == 2:
                return True
            try_cnt += 1

        if not return_flag:
            return False

        if order[0].get_attribute("href") and not "java" in order[0].get_attribute("href"):
            payment_url = order[0].get_attribute("href")

        '''paying or clicking place order for paying...'''
        try:
            order[0].click()
        except:
            driver.execute_script("arguments[0].click();", order[0])
            pass

        time.sleep(context.delaying_time-2)

        if self.check_alert_text(driver):
            return True

        checked_error = self.check_error(driver, context)

        if not checked_error:
            return False
        elif checked_error == 2:
            return True

        '''paying if payment info is not inputed'''
        if payment_url:
            driver.get(payment_url)

        if not is_paymentinfo:
            for _ in range(0, 3):
                pay_button = []

                if not self.fill_payment_info(driver, context) and not self.check_iframe_and_fill(driver, context):
                    logging.debug("Payment information is already inputed or payment field not exist!")
                else:
                    is_paymentinfo = True
                    context.log_step("Fill payment info fields")

                if return_flag:
                    for button in find_buttons(driver,["pay", "order", "submit"], ["border"]):
                        if button.get_attribute('href') == normalize_url(get_url(driver)):
                            continue
                        pay_button.append(button)
                if pay_button:
                    self.check_agree_and_click(driver)
                    if not self.click_one_element(pay_button):
                        if self.click_continue_in_iframe(driver):
                            return_flag = True
                            continue
                        logging.debug("Pay or order button error!")
                        return_flag = False
                    else:
                        return_flag = True
                        time.sleep(1)
                else:
                    if not self.click_continue_in_iframe(driver):
                        return_flag = False
                    else:
                        return_flag = True

        checked_error = self.check_error(driver, context)
        if return_flag or checked_error == 2:
            return_flag = True
        elif not return_flag and checked_error == 1:
            blog_text = get_page_text(driver)
            if nlp.check_text(blog_text, ["thank(s|)\s.*purchase"]):
                return_flag = True
        return return_flag

    def process_page(self, driver, state, context):
        #the case if authentication is requiring, pass authentication by creating an account as guest...
        time.sleep(3)
        radio_pass = self.find_radio_continue_buttons(driver)

        if radio_pass:
            #click an radio as guest....
            if not click_first(driver, radio_pass):
                return state
            time.sleep(1)

        continue_pass = self.find_guess_continue_button(driver)

        if continue_pass:
            #Fill email field if exist...
            guest_email = []

            for email in driver.find_elements_by_css_selector("input[type='email']"):
                if can_click(email):
                    guest_email.append(email)

            if guest_email:
                for g_email in guest_email:
                    g_email.send_keys(context.user_info.email)

            time.sleep(1)
            #click continue button for guest....
            try:
                continue_pass[0].click()
            except:
                driver.execute_script("arguments[0].click();", continue_pass[0])
                pass

            time.sleep(1)

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
