from selenium import webdriver
from bs4 import BeautifulSoup
import logging
import traceback
import tempfile
import os
from PIL import Image
import time

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.expected_conditions import *
from selenium.webdriver.common.alert import *
from selenium.webdriver.support.expected_conditions import staleness_of


class Frame:
    def __init__(self, driver, frame=None):
        self.driver = driver
        self.frame = frame

    def __enter__(self):
        if self.frame:
            self.driver.switch_to.frame(self.frame)
            self.url = self.driver.current_url

    def __exit__(self, type, value, traceback):
        if self.frame:
            url = self.driver.current_url
            
            # ToDo Do checks without ancors
            if url == self.url: #and not is_stale(self.frame):
                self.driver.switch_to.default_content()


def is_stale(elem):
    try:
        tmp = elem.location
        tmp = elem.size
        return False
    except:
        logger = logging.getLogger('shop_tracer')
        exception = traceback.format_exc()
        logger.debug('during check if can click exception was thrown {}'.format(exception))
        return True
    

def can_click(element):
    try:
        return element.is_enabled() and element.is_displayed()
    except WebDriverException:
        logger = logging.getLogger('shop_tracer')
        exception = traceback.format_exc()
        logger.debug('during check if can click exception was thrown {}'.format(exception))

        return False


def find_alert(driver):    
    return alert_is_present()(driver)


def close_alert_if_appeared(driver):
    alert = find_alert(driver)
    if alert:
        logger = logging.getLogger('shop_tracer')
        logger.info('found alert with text {}'.format(alert.text))
        alert.dismiss()


def to_string(element):
    try:
        return element.get_attribute("outerHTML")
    except:
        return str(element)

    
def get_page_text(driver):
    html = driver.page_source
    soup = BeautifulSoup(html, 'lxml')
    
    for script in soup(["script", "style", "img", "input"]):
        script.decompose()
    
    return soup.get_text()

            
def count_tabs(driver):
    """
    Returns number of opened tabs on current page
    :param driver:   Web driver
    :return:         Number of opened tabs
    """
    return len(driver.window_handles)


def new_tab(driver):
    """
    Opens new tab in driver
    :param driver:   Web driver
    """
    driver.execute_script("window.open('');")
    handles = list(driver.window_handles)
    driver.switch_to_window(handles[-1])

    
def close_tab(driver):
    """
    Closes last opened tab
    :param driver:    Web driver
    """
    handles = list(driver.window_handles)
    if len(handles) <= 1:
        return
    
    driver.switch_to_window(handles[-1])
    driver.close()
    driver.switch_to_window(handles[-2])


def get_element_attribute(element):
    if element.get_attribute('id'):
        return ['id', element.get_attribute('id')]
    elif element.get_attribute('name'):
        return ['name', element.get_attribute('name')]
    elif element.get_attribute('value'):
        return ['value', element.get_attribute('value')]

    return None


def create_chrome_driver(chrome_path='/usr/bin/chromedriver', headless=True, size = None):
    """
    Creates Chrome Web driver
    :param chrome_path:   Path to Chrome Web Driver binary
    :param headless:      Should be the driver headless or not
    :param size:          Tuple of page size
    :return:              Web driver
    """
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless')

    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    if not size:
        options.add_argument("--start-maximized")
    else:
        options.add_argument("--window-size={}x{}".format(size[0], size[1]));

    options.add_argument("--disable-web-security")
    options.add_argument("--ignore-certificate-errors");
    
    options.add_argument("--no-proxy-server")
    options.add_argument("--enable-automation")
    options.add_argument("--disable-save-password-bubble")
    options.add_argument("--crash-on-hang-threads")
    
    options.add_argument("--lang=en")
    
    
    return webdriver.Chrome(chrome_path, chrome_options=options)


def back(driver):
    """
    Press Back in web driver
    :param driver:   Web driver
    """
    driver.execute_script("window.history.go(-1)")

    
def get_frames(driver):
    """
    Returns all frames on current page
    :param driver:  Web driver
    :return:        List of web elements of frames
    """
    return [None] + \
        driver.find_elements_by_tag_name("iframe") + \
        driver.find_elements_by_tag_name("frame")


def get_screenshot(driver, file_to_save = None):
    """
    Returns screenshot of the current viewport
    :param driver:        Web driver
    :param file_to_save:  File to save
    :return:              Binary file representation
    """
    png = driver.get_screenshot_as_png()
    if file_to_save:
        with open(file_to_save, "wb") as file:
            file.write(png)

    return png


def get_current_scroll(driver):
    """
    Position from top
    :param driver:  Web driver
    :return:        Scroll distance from the top of the page from current scroll position
    """
    return driver.execute_script('return document.documentElement.scrollTop')


def get_page_height(driver):
    """
    Calculates full page height
    :param driver:  Web driver
    :return:        Full page height
    """
    return driver.execute_script('return document.body.parentNode.scrollHeight')


def get_window_height(driver):
    """
    Returns correct viewport height
    :param driver:  Web driver
    :return:        Correct Page height
    """
    return driver.execute_script('return window.innerHeight')


def scroll(driver, dw, dh):
    """
    Move scroll
    :param driver:  Web driver
    :param dw:      Diff of the left coordinate
    :param dh:      Diff of the top coordinate
    """
    driver.execute_script('window.scrollBy({}, {})'.format(dw, dh))


def get_scroll_top(driver):
    return driver.execute_script('return Math.max(document.documentElement.scrollTop, document.body.scrollTop);')


def scroll_to(driver, top):
    driver.execute_script("document.body.scrollTop = document.documentElement.scrollTop = {};".format(top))


def scroll_to_top(driver):
    scroll_to(driver, 0)


def get_scale(driver):
    """
    Calculates scale between screenshot size and page size
    :param driver:   Web driver
    :return:         Screenshot width / page width
    """
    fd, path = tempfile.mkstemp(prefix='screenshot', suffix='.png')
    os.close(fd)

    driver.save_screenshot(path)
    w, h = Image.open(path).size
    
    iw, ih = driver.execute_script("var w=window; return [w.innerWidth, w.innerHeight];")
    
    scale = w / iw
    assert abs(scale - h/ih) <= 1e-5
    
    return scale


def enter_text(driver, x, y, text):
    """
    Enters text to text field
    :param driver:   Web driver
    :param x:        Left for any point of the text field
    :param y:        Top for any point of the text field
    :param text:     Text to input
    """
    driver.execute_script('el = document.elementFromPoint({}, {}); el.value = "{}";'.format(x, y, text))


def get_full_page_screenshot(driver, output_file, scale):
    """
    Takes correct screenshot with scrolls and dynamic content
    :param driver:       Web driver
    :param output_file:  File to save screenshot
    :param scale:        Screenshot width / page width
                         Should be calculated using method get_scale(driver)
    """
    screens = []
        
    def save_screenshot():        
        fd, path = tempfile.mkstemp(prefix='screenshot', suffix='.png')
        os.close(fd)
        driver.save_screenshot(path)
        screens.append(path)
        
        return path
    
    try:
        scroll_to_top(driver)

        # take screenshots
        height = get_window_height(driver)
        scrolled = height
        save_screenshot()
        
        while scrolled < get_page_height(driver):
            scroll(driver, 0, height)
            time.sleep(0.1)
            save_screenshot()
            
            scrolled = min(scrolled + height, get_page_height(driver))
            
        # stitch images together
        stiched = None
        
        for i, screen in enumerate(screens):
            img = Image.open(screen)
             
            w, h = img.size
            y = i * height * scale
             
            if i == len(screens) - 1:
                w = w * scale
                h = h * scale  
                img = img.crop((0, h-(round(scale * scrolled)) % h, w, h))
                w, h = img.size
            
            if stiched is None:
                stiched = Image.new('RGB', (w, round(scrolled * scale)))
             
            stiched.paste(img, (
                0, # x0
                round(y), # y0
                w, # x1
                round(y + h) # y1
            ))
            
        stiched.save(output_file)
        
    finally:
        # cleanup
        for screen in screens:
            if os.path.isfile(screen):
                os.remove(screen)
 
    return output_file

