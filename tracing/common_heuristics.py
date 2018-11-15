import random

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains

from tracing.selenium_utils.common import *
from tracing.selenium_utils.controls import *
import tracing.nlp as nlp



def get_label_text_with_attribute(driver, elem):
    label_text = ""
    element_attribute = get_element_attribute(elem)

    try:
        if element_attribute:
            if element_attribute[0] == "id":
                label = driver.find_elements_by_css_selector("label[for='%s']" % element_attribute[1])
                if label:
                    label_text = nlp.remove_letters(label[0].get_attribute("innerHTML").strip(), ["/", "*", "-", "_", ":", " "]).lower()
                    return label_text

        label_text = nlp.remove_letters(
                elem.get_attribute("outerHTML").strip(),
                ["*", "-", "_", ":", " "]
        ).lower()
    except:
        label_text = ""

    return label_text


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
        else:
            l_text = get_label_text_with_attribute(driver, elem)

            if l_text and nlp.check_text(l_text, contains, not_contains):
                result.append(elem)
    
    return result


def get_no_href_buttons(driver, contains, not_contains=None, get_type = 1):
        '''
            Find no href link or button based on contains and not_contains parameters.
        '''
        result = []

        if get_type == 1:
            elements = find_buttons_or_links(driver, contains, not_contains)
        else:
            elements = find_buttons(driver, contains, not_contains)

        for btn in elements:
            if btn.get_attribute('href') == normalize_url(get_url(driver)):
                continue
            result.append(btn)

        return result


def find_elements_with_attribute(driver,
                                attr_tagname,
                                attr_type,
                                attr_content):
    return driver.find_elements_by_css_selector("{}[{}='{}']".format(attr_tagname, attr_type, attr_content))


def find_links(driver, contains=None, not_contains=None):
    result = []

    for link in get_links(driver):
        if not can_click(link):
            continue
            
        if get_url(driver) == link.get_attribute("href"):
            continue

        text = link.get_attribute("outerHTML")
        if nlp.check_text(text, contains, not_contains):
            result.append(link)

    return result


def find_error_elements(driver, contains=None, not_contains=None):
    divs = driver.find_elements_by_css_selector("div")
    spans = driver.find_elements_by_css_selector("span")
    label = driver.find_elements_by_css_selector("label")
    p = driver.find_elements_by_css_selector("p")
    ul = driver.find_elements_by_css_selector("ul")

    # Yield isn't good because context can change
    result = []
    try:
        for div in divs + spans + label + p + ul:
            if div.is_displayed():
                div_class = div.get_attribute("class")
                if nlp.check_text(div_class, contains, not_contains) and \
                    (div.get_attribute("innerHTML").strip() and not "error hide" in div.get_attribute("innerHTML").strip().lower()):
                    result.append(div)
    except:
        result = []
        pass
    return result


def find_sub_elements(driver, element, contains=None, not_contains=None):
    links = [elem for elem in element.find_elements_by_tag_name("a") if not is_link(driver, elem)]
    buttons = element.find_elements_by_tag_name("button")
    inputs = element.find_elements_by_css_selector('input[type="button"]')
    submits = element.find_elements_by_css_selector('input[type="submit"]')
    imgs = element.find_elements_by_css_selector('input[type="image"]')

    # Yield isn't good because context can change
    result = []
    for elem in links + buttons + inputs + submits + links + imgs:
        if not can_click(elem):
            continue

        text = elem.get_attribute("outerHTML")
        if nlp.check_text(text, contains, not_contains):
            result.append(elem)

    return result


def find_buttons(driver, contains=None, not_contains=None):
    
    # Yield isn't good because context can change
    result = []
    for elem in get_buttons(driver):
        if not can_click(elem):
            continue
        text = elem.get_attribute("innerHTML").strip() + \
               elem.text + " " + \
               (elem.get_attribute("value") if elem.get_attribute("value")  else "")
        if nlp.check_text(text, contains, not_contains):
            result.append(elem)

    return result


def find_buttons_or_links(driver, contains=None, not_contains=None):
    return find_links(driver, contains, not_contains) + \
            find_buttons(driver, contains, not_contains)


def try_handle_popups(driver):
    contains = ["i (.* |)over", "i (.* |)age", "i (.* |)year", "agree", "accept", "enter "]
    not_contains = ["not ", "under ", "leave", "login", "log in", "cancel"]
    
    btns = find_buttons_or_links(driver, contains, not_contains)
    if len(btns):
        checkbtns = find_radio_or_checkbox_buttons(driver, contains, not_contains)
        click_first(driver, checkbtns, None)
                
    
    result = click_first(driver, btns, None)
    if result:
        time.sleep(2)
    
    return result


def click_first(driver, elements, on_error=try_handle_popups, randomize = False):
    def process(element):
        try:
            # process links by opening url
            href = element.get_attribute("href")
            if is_link(element):
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

def find_text_element(driver, contains=None, not_contains=None):
    label = driver.find_elements_by_tag_name('label')
    h_elements = driver.find_elements_by_tag_name('h')
    span = driver.find_elements_by_tag_name('span')
    p = driver.find_elements_by_tag_name('p')
    td = driver.find_elements_by_tag_name('td')
    li = driver.find_elements_by_css_selector('li')

    for ind in range(1,6):
        h_elements += driver.find_elements_by_tag_name('h%s' % str(ind))

    result = None
    for elem in label + h_elements + span + p + td + li:
        text = elem.get_attribute("outerHTML")

        if nlp.check_text(text, contains, not_contains):
            result = elem

    return result


def is_empty_cart(driver):
    text = get_page_text(driver)
    return nlp.check_if_empty_cart(text)


def is_domain_for_sale(driver, domain):
    text = get_page_text(driver)
    return nlp.check_if_domain_for_sale(text, domain)

