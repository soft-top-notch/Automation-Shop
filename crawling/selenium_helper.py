from selenium import webdriver
from bs4 import BeautifulSoup

class Frame:
    def __init__(self, driver, frame=None):
        self.driver = driver
        self.frame = frame

    def __enter__(self):
        if self.frame:
            self.driver.switch_to.frame(self.frame)

    def __exit__(self, type, value, traceback):
        if self.frame:
            self.driver.switch_to.default_content()


def get_page_text(driver):
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    
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
    default_handle = driver.current_window_handle
    handles = list(driver.window_handles)
    if len(handles) <= 1:
        return
    
    handles.remove(default_handle)
    assert len(handles) > 0

    driver.switch_to_window(handles[0])
    driver.close()
    driver.switch_to_window(default_handle)

    
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
