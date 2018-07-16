from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException
import logging
import traceback
import wrapt
from selenium.webdriver.support.expected_conditions import *
from selenium.webdriver.common.alert import *


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
            if url == self.url:
                self.driver.switch_to.default_content()

def can_click(element):
    try:
        return element.is_enabled() and element.is_displayed()
    except WebDriverException:
        logger = logging.getLogger('shop_crawler')
        return False
    
    
def get_page_text(driver):
    html = driver.page_source
    soup = BeautifulSoup(html, 'lxml')
    
    for script in soup(["script", "style", "img", "input"]):
        script.decompose()
    
    return soup.get_text()

            
def count_tabs(driver):
    return len(driver.window_handles)


def new_tab(driver):
    driver.execute_script("window.open('');")
    handles = list(driver.window_handles)
    driver.switch_to_window(handles[-1])

    
def close_tab(driver):
    handles = list(driver.window_handles)
    if len(handles) <= 1:
        return
    
    driver.switch_to_window(handles[-1])
    driver.close()
    driver.switch_to_window(handles[-2])

    
def create_chrome_driver(chrome_path, headless=True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless')

    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-web-security")
    options.add_argument("--no-proxy-server")
    options.add_argument("--enable-automation")
    options.add_argument("--disable-save-password-bubble")

    return webdriver.Chrome(chrome_path, chrome_options=options)

def back(driver):
     driver.execute_script("window.history.go(-1)")

def find_alert(driver):    
    return alert_is_present()(driver)
