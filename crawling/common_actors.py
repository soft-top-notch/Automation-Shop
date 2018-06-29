from shop_crawler import *

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select

import sys
import re
import traceback


def normalize_text(text):
    # ToDo Proper normalization
    return text.replace('-', ' ') \
        .replace('_', ' ') \
        .replace('  ', ' ')


def check_text(text, contains, not_contains, normalize=True):
    if not contains:
        contains = []

    if not not_contains:
        not_contains = []

    if normalize:
        text = normalize_text(text)

    has_searched = False
    for str in contains:
        if re.search(str, text):
            has_searched = True
            break

    if not has_searched:
        return False

    has_forbidden = False
    for str in not_contains:
        if re.search(str, text):
            has_forbidden = True
            break

    return not has_forbidden


def can_click(element):
    try:
        element.is_enabled();
        return element.is_displayed()
    except:
        return False


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

        text = text.lower()
        if check_text(text, contains, not_contains):
            result.append(link)

    return result


def find_buttons_or_links(driver,
                          contains=None,
                          not_contains=None):
    links = driver.find_elements_by_css_selector("a[href]")
    buttons = driver.find_elements_by_css_selector("button")
    inputs = driver.find_elements_by_css_selector('input[type="button"]')
    submits = driver.find_elements_by_css_selector('input[type="submit"]')

    # Yield isn't good because context can change
    result = []
    for elem in links + buttons + inputs + submits:
        if not can_click(elem):
            continue

        text = elem.get_attribute("outerHTML").lower()
        if check_text(text, contains, not_contains):
            result.append(elem)

    return result


def click_first(driver, elements, on_error=None):
    def process(element):
        try:
            # process links by opening url
            href = element.get_attribute("href")
            if href and driver.current_url != href:
                driver.get(href)
                return True

            actions = ActionChains(driver)
            actions.move_to_element(element).perform()

            ActionChains(driver).move_to_element(element).perform()

            old_windows = len(driver.window_handles)
            element.click()
            new_windows = len(driver.window_handles)

            if new_windows > old_windows:
                driver.switch_to_window(driver.window_handles[-1])

            return True
        except:
            print("Unexpected error:", traceback.format_exc())
            return False

    for element in elements:
        if process(element):
            return True

        if on_error and on_error(driver):
            if process(element):
                return True

    return False


def try_handle_popups(driver):
    btns = find_buttons_or_links(driver, ["i .*over", "i .*age", "i agree"], [' .*not.*', " .*under.*"])
    return click_first(driver, btns)


class ToProductPage(IStepActor):
    def get_states(self):
        return [States.new, States.shop]

    def find_to_product_links(self, driver):
        return find_links(driver, ['/product', '/commodity', '/drug'], by_path=True)

    def filter_page(self, driver, state, context):
        links = self.find_to_product_links(driver)
        return len(links) > 0

    def process_page(self, driver, state, context):
        links = self.find_to_product_links(driver)
        if click_first(driver, links):
            return States.product_page
        else:
            return state


class AddToCart(IStepActor):
    def get_states(self):
        return [States.new, States.shop, States.product_page]

    def find_to_cart_elements(self, driver):
        return find_buttons_or_links(driver, ["add.*to.*cart",
                                              "add.*to.*bag"
                                              ])

    def filter_page(self, driver, state, content):
        elements = self.find_to_cart_elements(driver)
        return len(elements) > 0

    def process_page(self, driver, state, context):
        elements = self.find_to_cart_elements(driver)
        if click_first(driver, elements, try_handle_popups):
            return States.product_in_cart
        else:
            return state


class ToShop(IStepActor):
    def get_states(self):
        return [States.new]

    def find_to_shop_elements(self, driver):
        return find_buttons_or_links(driver, ["shop", "store", "products"], ["shops", "stores"])

    def filter_page(self, driver, state, context):
        elements = self.find_to_shop_elements(driver)
        return len(elements) > 0

    def process_page(self, driver, state, context):
        elements = self.find_to_shop_elements(driver)
        if click_first(driver, elements, try_handle_popups):
            return States.shop
        else:
            return state


class ToCart(IStepActor):

    def find_to_cart_elements(self, driver):
        return find_buttons_or_links(driver, ["cart"], ['add', 'append'])

    def get_states(self):
        return [States.product_in_cart]

    def filter_page(self, driver, state, context):
        btns = self.find_to_cart_elements(driver)
        return len(btns) > 0

    def process_page(self, driver, state, context):
        btns = self.find_to_cart_elements(driver)

        if click_first(driver, btns):
            return States.cart_page
        else:
            return state


class ToCartLink(IStepActor):
    def find_to_cart_links(self, driver):
        return find_links(driver, ["cart"], ['add', 'append'], by_path=True)

    def get_states(self):
        return [States.product_in_cart]

    def filter_page(self, driver, state, context):
        btns = self.find_to_cart_links(driver)
        return len(btns) > 0

    def process_page(self, driver, state, context):
        btns = self.find_to_cart_links(driver)

        if click_first(driver, btns):
            return States.cart_page
        else:
            return state


class ToCheckout(IStepActor):

    def find_checkout_elements(self, driver):
        return find_buttons_or_links(driver, ["checkout", "check out"])

    def get_states(self):
        return [States.product_in_cart, States.cart_page]

    def filter_page(self, driver, state, context):
        btns = self.find_checkout_elements(driver)
        return len(btns) > 0

    def process_page(self, driver, state, context):
        btns = self.find_checkout_elements(driver)

        if click_first(driver, btns):
            return States.checkout_page
        else:
            return state


def add_crawler_extensions(crawler):
    common_actors = [
        (3, AddToCart()),
        (2, ToProductPage()),
        (1, ToShop()),
        (3, ToCheckout()),
        (2, ToCartLink())
    ]

    for priority, handler in common_actors:
        crawler.add_handler(handler, priority)
