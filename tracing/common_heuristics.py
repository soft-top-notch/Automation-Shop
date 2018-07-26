from selenium_helper import *
import nlp
import time
import logging
import random

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains


def find_radio_or_checkbox_buttons(driver,
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


def normalize_url(url):
    if not url:
        return url
    
    return url[:url.index('#')] if '#' in url else url


def is_link(driver, elem):
    try:
        href = elem.get_attribute('href')
        href = normalize_url(href)
        return href and not href.startswith('javascript:') and href != driver.current_url
    except:
        logger = logging.getLogger('shop_tracer')
        logger.debug('Unexpected exception during check if element is link {}'.format(traceback.format_exc()))
        return False


def find_links(driver, contains=None, not_contains=None):
    links = driver.find_elements_by_css_selector("a[href]")
    result = []
    for link in links:
        if not can_click(link) or not is_link(driver, link):
            continue

        if driver.current_url == link.get_attribute("href"):
            continue

        text = link.get_attribute("outerHTML")
        if nlp.check_text(text, contains, not_contains):
            result.append(link)

    return result


def find_buttons(driver, contains=None, not_contains=None):
    
    links = [elem for elem in driver.find_elements_by_tag_name("a") if not is_link(driver, elem)]
    buttons = driver.find_elements_by_tag_name("button")
    inputs = driver.find_elements_by_css_selector('input[type="button"]')
    submits = driver.find_elements_by_css_selector('input[type="submit"]')
    imgs = driver.find_elements_by_css_selector('input[type="image"]')

    # Yield isn't good because context can change
    result = []
    for elem in links + buttons + inputs + submits + links + imgs:
        if not can_click(elem):
            continue

        text = elem.get_attribute("outerHTML")
        if nlp.check_text(text, contains, not_contains):
            result.append(elem)

    return result


def find_buttons_or_links(driver, contains=None, not_contains=None):
    return find_links(driver, contains, not_contains) + \
            find_buttons(driver, contains, not_contains)

def click_first(driver, elements, on_error=None, randomize = False):
    def process(element):
        try:
            # process links by opening url
            href = element.get_attribute("href")
            if is_link(driver, element):
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
            logger = logging.getLogger('shop_tracer')
            logger.debug('Unexpected exception during clicking element {}'.format(traceback.format_exc()))
            return False

    logger = logging.getLogger('shop_tracer')
    
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
    contains = ["i (.* |)over", "i (.* |)age", "i (.* |)year", "agree", "accept", "enter "]
    not_contains = ["not ", "under ", "leave", "login", "log in", "cancel"]
    
    btns = find_buttons_or_links(driver, contains, not_contains)
    if len(btns):
        checkbtns = find_radio_or_checkbox_buttons(driver, contains, not_contains)
        click_first(driver, checkbtns)
                
    result = click_first(driver, btns)
    if result:
        time.sleep(2)
    
    return result
