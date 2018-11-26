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
    not_contains = ['review', 'viewbox', 'view my shopping cart']

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
    type_list = [
        controls.Types.link,
        controls.Types.button
    ]
    contains =  ["addtocart", "addtobag", "add to cart", "add to bag"]
    not_contains = ["where", "about us"]

    def get_states(self):
        return [States.new, States.shop, States.product_page]

    @staticmethod
    def find_to_cart_elements(driver):
        return search_for_add_to_cart(driver)

    def get_action(self, control):

        if control.type not in self.type_list:
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
    type_list = [
        controls.Types.link,
        controls.Types.button
    ]
    contains = ["shop", "store", "products"]
    not_contains = ["shops", "stores", "shopping", "condition", "policy"]

    def get_states(self):
        return [States.new]

    def get_action(self, control):
        if control.type not in self.type_list:
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
    type_list = [
        controls.Types.link,
        controls.Types.button,
        controls.Types.radiobutton,
        controls.Types.checkbox
    ]
    contains = ["i (. |)over", "i (. |)age", "i (.* |)year", "agree", "accept", "enter "]
    not_contains = ["not ", "under ", "leave", "login", "log in", "cancel", " none"]

    def get_states(self):
        return [States.new]

    def get_action(self, control):
        if control.type not in self.type_list:
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
    type_list = [
        controls.Types.link,
    ]
    contains = ["cart"]
    not_contains = ["add", "append", "remove", "showcart"]

    def get_states(self):
        return [States.product_in_cart]
    
    def get_action(self, control):

        if control.type not in self.type_list:
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
    type_list = [
        controls.Types.link,
        controls.Types.button
    ]
    contains =  ["checkout", "check out"]
    not_contains = [
        'continue shopping', 'return',
        'guideline', 'login', 'log in',
        'sign in', 'view cart', 'logo', '/cart'
    ]

    def __init__(self):
        self.discard_count = 0  

    @staticmethod
    def find_checkout_elements(driver):
        btns = find_buttons_or_links(driver, ToCheckout.contains, ToCheckout.not_contains)

        # if there are buttongs that contains words in text return them first
        exact = []
        for btn in btns:
            text = btn.get_attribute('innerHTML')
            if nlp.check_text(text.lower(), ToCheckout.contains, ToCheckout.not_contains):
                exact.append(btn)

        if len(exact) > 0:
            return exact

        return btns

    def get_states(self):
        return [States.product_in_cart, States.cart_page]

    def get_action(self, control):
        if control.type not in self.type_list:
            return Nothing()

        text = control.label
        full_text = control.elem.get_attribute('outerHTML')
        if not text or not text.strip():
            text = control.elem.get_attribute('outerHTML')

        if nlp.check_text(text.lower(), self.contains, self.not_contains) and nlp.check_text(full_text.lower(), self.contains, self.not_contains):
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

    def __init__(self):
        self.guest_found = False
        self.user_name_found = False
        self.password_found = False
        self.country_filled = False

    def __str__(self):
        return "CheckoutLogin"

    def get_states(self):
        return [States.checkoutLoginPage]

    def get_action(self, control):
        if control.type not in [controls.Types.link, controls.Types.button, controls.Types.radiobutton, controls.Types.text]:
            if control.type == controls.Types.select:
                if (control.values and 'Colorado' in control.values) or \
                        (control.label and ('state' in control.label.lower() or 'province' in control.label.lower())):
                    return Nothing()
                elif 'United States of America' in control.values:
                    self.country_filled = True
                    return InputSelectField('select-country-full')
                elif 'United States America' in control.values:
                    self.country_filled = True
                    return InputSelectField('select-country-full-short')
                elif 'United States' in control.values:
                    self.country_filled = True
                    return InputSelectField('select-country-short')
                elif 'USA' in control.values:
                    self.country_filled = True
                    return InputSelectField('select-country-short-form')
            return Nothing()

        text = control.elem.get_attribute('outerHTML')

        if nlp.check_text(text.lower(), ['email', 'username'], self.not_contains):
            self.user_name_found = True
        if nlp.check_text(text.lower(), ['password'], self.not_contains):
            self.password_found = True
        if (control.label and nlp.check_text(control.label.lower(), ['guest', 'skip login'], self.not_contains)) or (control.label and 'skip login' in control.label.lower()):
            self.guest_found = True
            return Click()
        elif self.guest_found and control.label and nlp.check_text(control.label, self.contains, self.not_contains):
            return Click()
        elif control.label and "place order" in control.label.lower():
            # return MarkAsSuccess()
            return Click()

        else:
            if control.label and nlp.check_text(control.label, self.contains, self.not_contains):
                if not self.guest_found:
                    if self.user_name_found and self.password_found:
                        return Nothing()
                    else:
                        return Click()

            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):

        if not is_success:
            return (state, False)
        try:

            if self.guest_found:
                return (States.fillCheckoutPage, False)

            if nlp.check_text(control.label, self.contains, self.not_contains) or \
            "place order" in control.label.lower():
                if not environment.has_next_control():
                    # environment.refetch_controls()
                    return (States.fillCheckoutPage, False)
                else:
                    return (States.fillCheckoutPage, False)
            if not environment.has_next_control():
                return (States.fillCheckoutPage, False)
        except: pass

        return (state, False)


class FillingCheckoutPage(IEnvActor):
    type_list = [
        controls.Types.text, controls.Types.select, controls.Types.button, 
        controls.Types.link, controls.Types.radiobutton, controls.Types.checkbox
    ]
    contains = ['continue', 'payment', 'proceed', 'bill & ship']
    not_contains = ['amazon', 'paypal', 'giftcode', 'machine', 'cards']

    def __init__(self):
        self.state_control = None
        self.country_found = False

    def __str__(self):
        return "FillingCheckoutPage"

    def get_states(self):
        return [States.fillCheckoutPage]

    def get_action(self, control):
        if control.type not in self.type_list:
            return Nothing()

        if control.type == controls.Types.text:
            if not control.label:
                text = control.elem.get_attribute('outerHTML')
                # return Nothing()

            text = control.elem.get_attribute('outerHTML')
            if (control.label and nlp.check_text_with_label([text.lower(), control.label.lower()], ['first-name', 'first_name', 'first name', 'firstname', 'f_name', 'f-name', 'fname'], ['last_name'])) or nlp.check_text(text.lower(), ['first-name', 'first_name', 'first name', 'firstname', 'f_name', 'f-name', 'fname'], ['last_name']):
                return InputCheckoutFields("first_name")
            elif (control.label and nlp.check_text_with_label([text.lower(), control.label.lower()], ['last-name', 'last_name', 'last name', 'lastname', 'l_name', 'l-name', 'lname'], ['first_name'])) or nlp.check_text(text.lower(), ['last-name', 'last_name', 'last name', 'lastname', 'l_name', 'l-name', 'lname'], ['first_name']):
                return InputCheckoutFields("last_name")
            elif (control.label and nlp.check_text_with_label([text.lower(), control.label.lower()], ['email', 'e-mail', 'e_mail'], ['first_name', 'email_or_phone'])) or nlp.check_text(text.lower(), ['email', 'e-mail', 'e_mail'], ['first_name', 'email_or_phone']):
                return InputEmail()
            elif (control.label and nlp.check_text_with_label([text.lower(), control.label.lower()], ['street', 'road', 'address', 'apartment'], ['mail', 'pin code', 'postal', 'phone'])) or nlp.check_text(text.lower(), ['street', 'road', 'address', 'apartment'], ['mail', 'pin code', 'postal', 'phone']):
                return InputCheckoutFields("street")
            elif ('country' in text) and ('phone' not in text) :
                return InputCheckoutFields("country")
            elif (control.label and nlp.check_text_with_label([text.lower(), control.label.lower()], ['town', 'city'], ['mail'])) or nlp.check_text(text.lower(), ['town', 'city'], ['mail']):
                return InputCheckoutFields("city")
            elif (control.label and nlp.check_text_with_label([text.lower(), control.label.lower()], ['state', 'province', 'division'], ['mail'])) or nlp.check_text(text.lower(), ['state', 'province', 'division'], ['mail']):
                return InputCheckoutFields("state")
            elif (control.label and nlp.check_text_with_label([text.lower(), control.label.lower()], ['phone', 'mobile', 'telephone'])) or nlp.check_text(text.lower(), ['phone', 'mobile', 'telephone']):
                return InputCheckoutFields("phone")
            elif (control.label and nlp.check_text_with_label([text.lower(), control.label.lower()], ['post', 'zip'], ['submit'])) or nlp.check_text(text.lower(), ['post', 'zip'], ['submit']):
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
            if control.label and nlp.check_text(control.label.lower(), ['credit', 'checkout_braintree'], ['amazon', 'paypal']):
                return Click()
            else:
                return Nothing()
        elif control.type in [controls.Types.link, controls.Types.button]:
            text = control.elem.get_attribute('outerHTML')
            if (control.label and nlp.check_text(control.label.lower(), self.contains, self.not_contains)):
                if 'giftcode' in text.lower():
                    return Nothing()
                return Click()
            if (control.label and nlp.check_text(control.label.lower(), ['credit'], ['amazon', 'paypal', 'machine', 'cards'])):
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

            if control.label and nlp.check_text(control.label.lower(), ['credit', 'checkout_braintree'], ['amazon', 'paypal']):
                return (States.fillPaymentPage, False)

            if control.label and nlp.check_text(control.label.lower(), self.contains, self.not_contains):
                return (States.prePaymentFillingPage, False)
        except Exception as e:
            pass
        return (state, False)


class PrePaymentFillingPage(IEnvActor):
    type_list = [
        controls.Types.radiobutton,
        controls.Types.link,
        controls.Types.button
    ]
    contains = ['continue', 'proceed', 'ahead']
    not_contains = [
        'login', 'signin', 'log-in', 'sign-in', 'register', 'continue shopping'
    ]

    def __init__(self):
        self.card_text = ['credit card', 'credit-card', 'free']

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
        except:
            if nlp.check_text(control.label.lower(), ['payment method'], ['shipping']):
                return (States.fillPaymentPage, False)
            pass

        return (state, False)


class FillingPaymentPage(ISiteActor):
    type_list = [
        controls.Types.link, controls.Types.button,
        controls.Types.text, controls.Types.select, 
        controls.Types.radiobutton, controls.Types.checkbox
    ]
    contains = ['card type', 'credit-type', 'cctype']
    not_contains = ['sign-in', 'continue shopping']

    def __init__(self):
        self.init_variables()

    def __str__(self):
        return "FillingPaymentPage"

    def get_filling_status(self):
        return self.card_number_filled and self.card_cvc_filled and self.card_month_filled and self.card_year_filled

    def init_variables(self):
        self.flag = True
        self.has_card_details = False
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
                'card number', 'card-number', 'card_number', 'ccno'
            ]
            if nlp.check_text(text.lower(), card_number_text, ['sign-in']):
                self.card_number_filled = True
                self.has_card_details = True
                return InputPaymentTextField('card-number')
            elif (control.label and nlp.check_text(control.label.lower(), ['name on card'], ['card-number'])):
                return InputCheckoutFields("first_name")
            elif (control.label and nlp.check_text(control.label.lower(), ['verification', 'cvc', 'cvv', 'cccvd'], ['card-number'])) or nlp.check_text(text.lower(), ['verification', 'cvc', 'cvv', 'cccvd'], ['card-number']):
                self.card_cvc_filled = True
                return InputPaymentTextField('cvc')
            elif (control.label and ('mm' in control.label.lower() and 'yy' in control.label.lower())) or ('month' in text.lower() and 'year' in text.lower()) or ('mm' in text.lower() and 'yy' in text.lower()):
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
            elif nlp.check_text(text.lower(), ['expiration', 'expire', 'year', 'month', 'ccexpm', 'ccexpy'], ['credit-card-number']):
                if nlp.check_text(text.lower(), ['month', 'mm', 'ccexpm'], ['year']):
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
                elif nlp.check_text(text.lower(), ['year', 'yy', 'ccexpy'], ['month']):
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
            sub_contains = ['credit card', 'credit-card', 'free', 'liquid scentsations', 'braintree']
            sub_not_contains = ['number']

            if nlp.check_text(text.lower(), ['number'])\
                    or (control.label and nlp.check_text(control.label.lower(), sub_contains, sub_not_contains)):
                return Click()

            if 'different_billing_address_false' in text.lower():
                return Click()

            return Nothing()
        elif control.type in [controls.Types.button, controls.Types.link]:
            sub_contains = ['place order', 'continue', 'proceed', 'payment','pay for order']
            sub_not_contains = ['sign-in', 'continue shopping', 'paypal', 'cheque', 'moneyorder', 'gift', 'machine']
            if (control.label and nlp.check_text(control.label.lower(), sub_contains, sub_not_contains)) or nlp.check_text(text.lower(), sub_contains, sub_not_contains):
                if self.get_filling_status():
                    return Click()
                elif not self.has_card_details:
                    return Click()
                else:
                    self.place_order_control = control
                    return Nothing()

            return Nothing()
        elif control.type == controls.Types.checkbox:

            if control.label and nlp.check_text(text.lower(), ['agreetermsandconditions', 'terms and conditions'], ['amazon', 'paypal']):
                return Click()
            else:
                return Nothing()
        else:
            return Nothing()

    def get_state_after_action(self, is_success, state, control, environment):


        if not is_success:
            return (state, False)
        try:
            if control.label and nlp.check_text(control.label.lower(), ['proceed to payment'], self.not_contains):
                time.sleep(5)
            if control.type in [controls.Types.text, controls.Types.select, controls.Types.radiobutton]:
                text = control.elem.get_attribute('outerHTML')
                if (control.label and nlp.check_text(control.label.lower(), ['verification', 'cvc', 'cvv', 'cccvd'], ['card-number'])) or nlp.check_text(text.lower(), ['verification', 'cvc', 'cvv', 'cccvd'], ['card-number']):
                    if not environment.has_next_control():
                        environment.reset_control()
                else:
                    pass
            elif control.label and nlp.check_text(control.label.lower(), ['place order', 'pay for order'], self.not_contains):
                return (States.purchased, False)
            elif control.label and nlp.check_text(control.label.lower(), ['continue', 'order'], self.not_contains):
                text = control.elem.get_attribute('outerHTML')
                if 'credit card' in text.lower():
                    return (States.pay, False)
                if not self.get_filling_status():
                    if not self.has_card_details:
                        environment.refetch_controls()
                        # environment.reset_control()
                else:
                    if control.label and nlp.check_text(control.label.lower(), ['complete order'], self.not_contains):
                        return (States.purchased, False)
                    return (States.pay, False)
            elif self.get_filling_status():
                if environment.has_next_control():
                    next_ctrl = environment.get_next_control()
                    next_text = next_ctrl.elem.get_attribute('outerHTML')
                    if nlp.check_text(next_text.lower(), ['post code', 'zip', 'postal', 'post-code', 'post_code', 'postal code'], ['card-number']):
                        environment.apply_action(next_ctrl, InputPaymentTextField('cvc'))
                        return (States.pay, False)
                else:
                    self.flag = False
                    environment.reset_control()
            elif not self.get_filling_status():
                if not self.has_card_details:
                    environment.refetch_controls()
        except Exception as e:
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
