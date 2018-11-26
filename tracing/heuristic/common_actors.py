import random
import sys
import traceback
import time
import csv
import sys

from tracing.nlp import *
from tracing.common_heuristics import *

import tracing.selenium_utils.common as common
import tracing.selenium_utils.controls as controls
from tracing.heuristic.shop_tracer import *
from tracing.rl.actions import *
from tracing.rl.environment import *


class ToProductPageLink(IEnvActor):
    contains = ['/product', '/commodity', '/drug', 'details', 'view']
    not_contains = ['review', 'viewbox']

    def get_states(self):
        return [States.new, States.shop]

    def get_action(self, control):
        if control.type != controls.Types.link:
            return Nothing()
        
        text = control.elem.get_attribute('outerHTML')
        if nlp.check_text(text, self.contains, self.not_contains):
            return Click()
        else:
            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):
        if not is_success:
            return (state, False)
        
        if AddToCart.find_to_cart_elements(environment.driver):
            return (States.product_page, False)
        
        # Discard last action
        return (state, True)

    
class AddToCart(IEnvActor):
    contains =  ["addtocart", "addtobag", "add to cart", "add to bag"]
    not_contains = ["where", "about us"]

    def get_states(self):
        return [States.new, States.shop, States.product_page]

    @staticmethod
    def find_to_cart_elements(driver):
        return search_for_add_to_cart(driver)

    def get_action(self, control):

        if control.type not in [controls.Types.link, controls.Types.button]:
            return Nothing()
        try:
            text = control.label
            if not text or not text.strip():
                text = control.elem.get_attribute('outerHTML')

            if nlp.check_text(text, self.contains, self.not_contains):
                return Click()
            else:
                return Nothing()
        except:
            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):
        if not is_success:
            return (state, False)
        
        if not is_empty_cart(environment.driver):
            return (States.product_in_cart, False)
        return (state, True)


class ToShopLink(IEnvActor):
    contains = ["shop", "store", "products"]
    not_contains = ["shops", "stores", "shopping", "condition", "policy"]

    def get_states(self):
        return [States.new]

    def get_action(self, control):
        if control.type not in [controls.Types.link, controls.Types.button]:
            return Nothing()
        
        text = control.elem.get_attribute('outerHTML')
        if nlp.check_text(text, self.contains, self.not_contains):
            return Click()
        else:
            return Nothing()
    
    def get_state_after_action(self, is_success, state, control, environment):
        if not is_success:
            return (state, False)

        return (States.shop, False)


class ClosePopups(IEnvActor):
    contains = ["i (. |)over", "i (. |)age", "i (.* |)year", "agree", "accept", "enter "]
    not_contains = ["not ", "under ", "leave", "login", "log in", "cancel", " none"]

    def get_states(self):
        return [States.new]

    def get_action(self, control):
        if control.type not in [controls.Types.link, controls.Types.button, controls.Types.radiobutton, controls.Types.checkbox]:
            return Nothing()

        text = control.elem.get_attribute("innerHTML").strip() + \
               control.elem.text + " " + \
               (control.elem.get_attribute("value") if control.elem.get_attribute("value")  else "")

        if nlp.check_text(text, self.contains, self.not_contains):
            return Click()
        else:
            if control.type in [controls.Types.radiobutton, controls.Types.checkbox] and \
                nlp.check_text(controls.get_label(control.elem), self.contains, self.not_contains):
                return Click()
            return Nothing()
    
    def get_state_after_action(self, is_success, state, control, environment):
        return (state, False)

        
class ToCartLink(IEnvActor):
    contains = ["cart"]
    not_contains = ["add", "append"]

    def get_states(self):
        return [States.product_in_cart]
    
    def get_action(self, control):
        if control.type not in [controls.Types.link]:
            return Nothing()
        
        text = control.elem.get_attribute('outerHTML')
        if nlp.check_text(text, self.contains, self.not_contains):
            return Click()
        else:
            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):
        if not is_success:
            environment.states.append(())
            return (state, False)
        
        time.sleep(3)

        if not is_empty_cart(environment.driver) and ToCheckout.find_checkout_elements(environment.driver):
            return (States.cart_page, False)
        
        # Discard last action
        return (state, True)


class ToCheckout(IEnvActor):
    contains =  ["checkout", "check out"]
    not_contains = [
        'continue shopping', 'return',
        'guideline', 'login', 'log in',
        'sign in', 'view cart', 'logo'
    ]
    discard_count = 0

    @staticmethod
    def find_checkout_elements(driver):
        btns = find_buttons_or_links(driver, ToCheckout.contains, ToCheckout.not_contains)

        # if there are buttongs that contains words in text return them first
        exact = []
        for btn in btns:
            text = btn.get_attribute('innerHTML')
            if nlp.check_text(text, ToCheckout.contains, ToCheckout.not_contains):
                exact.append(btn)

        if len(exact) > 0:
            return exact

        return btns

    def get_states(self):
        return [States.product_in_cart, States.cart_page]

    def get_action(self, control):
        if control.type not in [controls.Types.link, controls.Types.button]:
            return Nothing()

        text = control.label
        if not text or not text.strip():
            text = control.elem.get_attribute('outerHTML')

        if nlp.check_text(text, self.contains, self.not_contains):
            return Click()
        else:
            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):
        if not is_success:
            return (state, False)
        
        time.sleep(3)
        close_alert_if_appeared(environment.driver)

        if ToCheckout.find_checkout_elements(environment.driver):
            if self.discard_count == 0:
                self.discard_count += 1
                return (state, True)
        # return (States.fillCheckoutPage, False)
        return (States.checkoutLoginPage, False)


class SearchForProductPage(ISiteActor):
    def get_states(self):
        return [States.new, States.shop]

    def get_action(self, environment):
        return SearchProductPage()

    def get_state_after_action(self, is_success, state, environment):
        if not is_success:
            return state
        
        if AddToCart.find_to_cart_elements(environment.driver):
            return States.product_page
        return state


class CheckoutLogin(IEnvActor):
    contains = ['continue', 'proceed', 'ahead']
    not_contains = [
        'login', 'signin', 'log-in', 'sign-in', 'register',
    ]
    guest_found = False

    def __str__(self):
        return "CheckoutLogin"

    def reset_flags(self):
        self.guest_found = False
        return

    def get_states(self):
        return [States.checkoutLoginPage]

    def get_action(self, control):
        if control.type not in [controls.Types.link, controls.Types.button, controls.Types.radiobutton]:
            return Nothing()

        # text = control.elem.get_attribute('outerHTML')

        if control.label and nlp.check_text(control.label, ['guest', 'skip login'], self.not_contains):
            self.guest_found = True
            return Click()
        elif self.guest_found and control.label and nlp.check_text(control.label, self.contains, self.not_contains):
            return Click()
        elif control.label and "place order" in control.label.lower():
            return MarkAsSuccess()

        else:
            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):
        if not is_success:
            return (state, False)
        try:
            if nlp.check_text(control.label, self.contains, self.not_contains) or \
            "place order" in control.label.lower():
                return (States.fillCheckoutPage, False)
        except: pass

        return (state, False)


class FillingCheckoutPage(IEnvActor):
    type_list = [
        controls.Types.text, controls.Types.select, controls.Types.button, 
        controls.Types.link, controls.Types.radiobutton
    ]
    contains = ['continue', 'payment', 'proceed', 'bill & ship']
    not_contains = ['amazon', 'paypal']
    state_control = None
    country_found = False

    def __str__(self):
        return "FillingCheckoutPage"

    def get_states(self):
        return [States.fillCheckoutPage]

    def get_action(self, control):
        if control.type not in self.type_list:
            return Nothing()

        if control.type == controls.Types.text:
            if not control.label:
                return Nothing()

            text = control.elem.get_attribute('outerHTML')
            if nlp.check_text(text, ['first-name', 'first_name', 'first name', 'firstname', 'f_name', 'f-name', 'fname'], ['last_name']):
                return InputCheckoutFields("first_name")
            elif nlp.check_text(text, ['last-name', 'last_name', 'last name', 'lastname', 'l_name', 'l-name', 'lname'], ['first_name']):
                return InputCheckoutFields("last_name")
            elif nlp.check_text(text, ['email', 'e-mail', 'e_mail'], ['name']):
                return InputEmail()
            elif nlp.check_text(text, ['street', 'road', 'address', 'apartment'], ['mail']):
                return InputCheckoutFields("street")
            elif 'country' in text:
                return InputCheckoutFields("country")
            elif nlp.check_text(text, ['town', 'city'], ['mail']):
                return InputCheckoutFields("city")
            elif nlp.check_text(text, ['state', 'province', 'division'], ['mail']):
                return InputCheckoutFields("state")
            elif nlp.check_text(text, ['phone', 'mobile', 'telephone'], ['address']):
                return InputCheckoutFields("phone")
            elif nlp.check_text(text, ['post', 'zip'], ['submit']):
                return InputCheckoutFields("zip")
            else:
                return Nothing()
        elif control.type == controls.Types.select:
            if (control.values and 'Colorado' in control.values) or \
                    (control.label and ('state' in control.label.lower() or 'province' in control.label.lower())):
                # return InputSelectField('select-state-name')
                self.state_control = control
                return Nothing()
            elif 'United States of America' in control.values:
                self.country_found = True
                return InputSelectField('select-country-full')
            elif 'United States America' in control.values:
                self.country_found = True
                return InputSelectField('select-country-full-short')
            elif 'United States' in control.values:
                self.country_found = True
                return InputSelectField('select-country-short')
            elif 'USA' in control.values:
                self.country_found = True
                return InputSelectField('select-country-short-form')
            return Nothing()
        elif control.type == controls.Types.radiobutton:
            if control.label and nlp.check_text(control.label.lower(), ['credit'], ['amazon', 'paypal']):
                return Click()
            else:
                return Nothing()
        elif control.type in [controls.Types.link, controls.Types.button]:
            if control.label and nlp.check_text(control.label.lower(), self.contains, self.not_contains):
                return Click()
            return Nothing()
        else:
            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):
        if not is_success:
            return (state, False)
        try:
            if self.country_found and self.state_control:
                environment.apply_action(self.state_control, InputSelectField('select-state-name'))
                self.state_control = None
                self.country_found = False

            if control.label and nlp.check_text(control.label.lower(), self.contains, self.not_contains):
                return (States.prePaymentFillingPage, False)
        except: pass
        return (state, False)


class PrePaymentFillingPage(IEnvActor):
    type_list = [controls.Types.radiobutton, controls.Types.link, controls.Types.button]
    contains = ['continue', 'proceed', 'ahead']
    not_contains = [
        'login', 'signin', 'log-in', 'sign-in', 'register', 'continue shopping'
    ]
    card_text = ['credit card', 'credit-card', 'free']

    def __str__(self):
        return "PrePaymentFillingPage"

    def get_states(self):
        return [States.prePaymentFillingPage]

    def get_action(self, control):
        if control.type not in self.type_list:
            return Nothing()

        text = control.elem.get_attribute('outerHTML')

        if (nlp.check_text(text.lower(), self.card_text + self.contains, self.not_contains)) or \
            (control.label and nlp.check_text(control.label.lower(), self.card_text, self.not_contains)):
            return Click()

        else:
            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):
        if not is_success:
            return (state, False)
        try:
            text = control.elem.get_attribute('outerHTML')

            if nlp.check_text(text.lower(), self.contains, self.not_contains):
                return (States.fillPaymentPage, False)
        except: pass

        return (state, False)


class FillingPaymentPage(ISiteActor):
    type_list = [
        controls.Types.link, controls.Types.button,
        controls.Types.text, controls.Types.select, 
        controls.Types.radiobutton
    ]
    contains = ['card type', 'credit-type']
    not_contains = ['sign-in', 'continue shopping']

    flag = True
    card_number_filled = False
    card_cvc_filled = False
    card_month_filled = False
    card_year_filled = False
    place_order_control = None

    def __str__(self):
        return "FillingPaymentPage"

    def get_filling_status(self):
        return self.card_number_filled and self.card_cvc_filled and self.card_month_filled and self.card_year_filled

    def reset_flags(self):
        self.flag = True
        self.card_number_filled = False
        self.card_cvc_filled = False
        self.card_month_filled = False
        self.card_year_filled = False
        self.place_order_control = None

    def get_states(self):
        return [States.fillPaymentPage]

    def get_action(self, control):
        if control.type not in self.type_list:
            if self.place_order_control and self.get_filling_status():
                return Click()
            return Nothing()
        elif self.place_order_control and self.get_filling_status():
            return Click()

        text = control.elem.get_attribute('outerHTML')

        if control.type == controls.Types.text:
            card_number_text = [
                'cc-number', 'cc_number', 'cc number', 
                'card number', 'card-number', 'card_number'
            ]

            if nlp.check_text(text, card_number_text, ['sign-in']):
                self.card_number_filled = True
                return InputPaymentTextField('card-number')
            elif nlp.check_text(text, ['verification', 'cvc', 'cvv'], ['card-number']):
                self.card_cvc_filled = True
                return InputPaymentTextField('cvc')
            elif ('month' in text and 'year' in text) or ('mm' in text and 'yy' in text):
                self.card_month_filled = True
                self.card_year_filled = True
                return InputPaymentTextField('input-card-month-year')
            elif 'month' in text:
                self.card_month_filled = True
                return InputPaymentTextField('input-card-month')
            elif 'year' in text:
                self.card_year_filled = True
                return InputPaymentTextField('input-card-year')
            elif nlp.check_text(text.lower(), ['post code', 'zip', 'postal', 'post-code', 'post_code'], ['card-number']):
                return InputCheckoutFields('zip')
            else:
                return Nothing()
        elif control.type == controls.Types.select:
            if nlp.check_text(text.lower(), self.contains, ['credit-card-number'])\
                    or control.label and nlp.check_text(control.label.lower(), self.contains, ['credit-card-number']):
                return InputSelectField('card-type')
            elif nlp.check_text(text.lower(), ['expiration', 'expire', 'year', 'month'], ['credit-card-number']):
                if nlp.check_text(text.lower(), ['month', 'mm'], ['year']):
                    self.card_month_filled = True
                    if '06 - June' in control.values:
                        return InputSelectField('expire-month-text-with-number-full')
                    elif '6 - June' in control.values:
                        return InputSelectField('expire-month-text-with-number-short')
                    elif 'June' in control.values:
                        return InputSelectField('expire-month-text-full')
                    elif 'Jun' in control.values:
                        return InputSelectField('expire-month-text-short')
                    elif '06' in control.values:
                        return InputSelectField('expire-month-number-full')
                    elif '6' in control.values:
                        return InputSelectField('expire-month-number-short')
                    else:
                        return InputSelectField('expire-month-text-full')
                elif nlp.check_text(text.lower(), ['year', 'yy'], ['month']):
                    self.card_year_filled = True
                    if '2021' in control.values:
                        return InputSelectField('expire-year-full')
                    elif '21' in control.values:
                        return InputSelectField('expire-year-short')
                    else:
                        return InputSelectField('expire-year-full')
                return Nothing()
            else:
                return Nothing()
        elif control.type == controls.Types.radiobutton:
            sub_contains = ['credit card', 'credit-card', 'free']
            sub_not_contains = ['number']

            if nlp.check_text(text.lower(), ['number'])\
                    or (control.label and nlp.check_text(control.label.lower(), sub_contains, sub_not_contains)):
                return Click()

            return Nothing()
        elif control.type in [controls.Types.button, controls.Types.link]:
            sub_contains = ['place order', 'continue']
            sub_not_contains = ['sign-in', 'continue shopping']

            if control.label and nlp.check_text(control.label.lower(), sub_contains, sub_not_contains):
                if self.get_filling_status():
                    return Click()
                else:
                    self.place_order_control = control
                    return Nothing()

            return Nothing()
        else:
            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):
        if not is_success:
            return (state, False)
        try:
            text = control.elem.get_attribute('outerHTML')

            if nlp.check_text(text.lower(), self.contains, ['number']) and self.flag or \
                (control.label and nlp.check_text(control.label.lower(), self.contains, ['number']) and self.flag):
                self.flag = False
                environment.reset_control()

            if control.label and nlp.check_text(control.label.lower(), ['place order'], self.not_contains):
                return (States.purchased, False)
            elif control.label and nlp.check_text(control.label.lower(), ['continue'], self.not_contains):
                return (States.pay, False)
        except:
            pass
        return (state, False)


class Pay(IEnvActor):
    type_list = [controls.Types.link, controls.Types.button]
    contains = ['continue', 'proceed', 'ahead', 'place', 'pay for order']
    not_contains = ['login', 'signin', 'log-in', 'sign-in', 'register', 'continue shopping']

    def __str__(self):
        return "Pay"

    def get_states(self):
        return [States.pay]

    def get_action(self, control):
        if control.type not in self.type_list:
            return Nothing()
        text = control.elem.get_attribute('outerHTML')

        if nlp.check_text(text.lower(), self.contains, self.not_contains):
            return Click()

        else:
            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):
        if not is_success:
            return (state, False)

        try:
            if control.label and nlp.check_text(control.label.lower(), self.contains, self.not_contains):
                return (States.purchased, False)
            text = control.elem.get_attribute('outerHTML')

            if nlp.check_text(text.lower(), self.contains, self.not_contains):
                return (States.purchased, False)
        except:
            pass

        return (state, False)


def add_tracer_extensions(tracer):
    # tracer.add_handler(ClosePopups(), 5)

    tracer.add_handler(AddToCart(), 4)
    tracer.add_handler(SearchForProductPage(), 1)
    tracer.add_handler(ToProductPageLink(), 3)
    tracer.add_handler(ToShopLink(), 2)

    tracer.add_handler(ToCheckout(), 3)
    tracer.add_handler(CheckoutLogin(), 2)
    tracer.add_handler(FillingCheckoutPage(), 2)
    tracer.add_handler(PrePaymentFillingPage(), 2)
    tracer.add_handler(FillingPaymentPage(), 2)
    tracer.add_handler(Pay(), 2)
    tracer.add_handler(ToCartLink(), 2)
