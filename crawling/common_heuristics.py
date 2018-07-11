from selenium_helper import *
import nlp

def is_empty_cart(driver):
    text = get_page_text(driver)
    return nlp.check_if_empty_cart(text)

def is_domain_for_sale(driver, domain):
    text = get_page_text(driver)
    return nlp.check_if_domain_for_sale(text, domain)

