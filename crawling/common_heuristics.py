from selenium_helper import *
import nlp
import time
import logging
import random

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains


def find_radio_or_checkout_button(driver,
                                  contains=None,
                                  not_contains=None):
    radiobtns = driver.find_elements_by_css_selector("input[type='radio']")
    checkbtns = driver.find_elements_by_css_selector("input[type='checkbox']")

    result = []
    for elem in radiobtns + checkbtns:
        text = elem.get_attribute("outerHTML")
        if nlp.check_text(text, contains, not_contains):
            result.append(elem)
    
    return result


def find_links(driver, contains=None, not_contains=None):
    links = driver.find_elements_by_css_selector("a[href]")
    result = []
    for link in links:
        if not can_click(link):
            continue

        href = link.get_attribute("href")
        if driver.current_url == href or not href:
            continue

        text = link.get_attribute("outerHTML")
        if nlp.check_text(text, contains, not_contains):
            result.append(link)

    return result


def find_buttons_or_links(driver,
                          contains=None,
                          not_contains=None
                         ):
    links = driver.find_elements_by_tag_name("a")
    buttons = driver.find_elements_by_tag_name("button")
    inputs = driver.find_elements_by_css_selector('input[type="button"]')
    submits = driver.find_elements_by_css_selector('input[type="submit"]')
    imgs = driver.find_elements_by_css_selector('input[type="image"]')

    # Yield isn't good because context can change
    result = []
    for elem in links + buttons + inputs + submits:
        if not can_click(elem):
            continue

        text = elem.get_attribute("outerHTML")
        if nlp.check_text(text, contains, not_contains):
            result.append(elem)

    return result


def click_first(driver, elements, on_error=None, randomize = False):
    def process(element):
        try:
            # process links by opening url
            href = element.get_attribute("href")
            if href and driver.current_url != href and not href.startswith('javascript:'):
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
    
    if randomize:
        random.shuffle(elements)
    
    for element in elements:
        logger.debug('clicking element: {}'.format(to_string(element)))
        clicked = process(element)
        logger.debug('result: {}'.format(clicked))
                     
        if clicked:
            return True

        if on_error:
            logger.debug('processing erorr')
            error_processed = on_error(driver)
            logger.debug('error process result: {}'.format(error_processed))
            
            logger.debug('clicking again')
            clicked = process(element)
            logger.debug('result: {}'.format(clicked))
            if clicked:
                return True

    return False



def is_empty_cart(driver):
    text = get_page_text(driver)
    return nlp.check_if_empty_cart(text)


def is_domain_for_sale(driver, domain):
    text = get_page_text(driver)
    return nlp.check_if_domain_for_sale(text, domain)


def try_handle_popups(driver):
    btns = find_buttons_or_links(driver, ["i .*over", "i .*age", "agree", "accept"], ["not ", "under "])
    result = click_first(driver, btns)
    if result:
        time.sleep(2)
    
    return result
