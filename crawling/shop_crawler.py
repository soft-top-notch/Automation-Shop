import logging
from abc import ABCMeta, abstractmethod
from selenium import webdriver
import sys
import time


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


class States:
    new = "new"
    shop = "shop"
    product_page = "product_page"
    product_in_cart = "product_in_cart"
    cart_page = "cart_page"
    checkout_page = "checkout_page"
    payment_page = "payment_page"
    purchased = "purchased"

    states = [new, product_page, product_in_cart, checkout_page, payment_page, purchased]


class UserInfo:
    def __init__(self,
                 first_name,
                 last_name,
                 home,
                 street,
                 zip,
                 city,
                 state,
                 country,
                 phone,
                 email
                 ):
        self.first_name = first_name
        self.last_name = last_name
        self.home = home
        self.street = street
        self.zip = zip
        self.state = state
        self.city = city
        self.country = country
        self.phone = phone
        self.email = email


class PaymentInfo:
    def __init__(self,
                 card_number,
                 expire_date_year,
                 expire_date_month,
                 cvc
                 ):
        self.card_number = card_number
        self.expire_date_year = expire_date_year
        self.expire_date_month = expire_date_month
        self.cvc = cvc


class StepContext:
    def __init__(self, user_info, payment_info):
        self.user_info = user_info
        self.payment_info = payment_info


class IStepActor:

    @abstractmethod
    def filter_page(self, driver, state, context):
        raise NotImplementedError

    @abstractmethod
    def process_page(self, driver, state, context):
        raise NotImplementedError

    @abstractmethod
    def get_states(self):
        raise NotImplementedError

    def can_handle(self, driver, state, context):
        states = self.get_states()

        if states and state not in states:
            return False

        return self.filter_page(driver, state, context)

    def act(self, driver, state, context):
        step = self.process_page(driver, state, context)
        return step


class ShopCrawler:
    def __init__(self, user_info, payment_info,
                 chrome_path='/usr/local/chromedriver',
                 headless=True
                 ):
        self._handlers = []
        self._user_info = user_info
        self._payment_info = payment_info
        self._chrome_path = chrome_path
        self._logger = logging.getLogger('PageHandler')
        self._headless = headless

    def add_handler(self, actor, priority=1):
        assert priority >= 1 and priority <= 10, \
            "Priority should be between 1 and 10 while got {}".format(priority)
        self._handlers.append((priority, actor))

    @staticmethod
    def normalize_url(url):
        if url.startswith('http://') or url.startswith('https://'):
            return url
        return 'http://' + url

    @staticmethod
    def create_driver():
        options = webdriver.ChromeOptions()
        if self._headless:
            options.add_argument('--headless')

        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-web-security")
        options.add_argument("--no-proxy-server")
        options.add_argument("--enable-automation")
        options.add_argument("--disable-save-password-bubble")

        driver = webdriver.Chrome(self._chrome_path, chrome_options=options)
        
        return driver
    
    def process_state(self, driver, state):
        context = StepContext(self._user_info, self._payment_info)

        handlers = [(priority, handler) for priority, handler in self._handlers
                    if handler.can_handle(driver, state, context)]

        handlers.sort(key=lambda p: -p[0])

        print('processing state: {}'.format(state))

        for priority, handler in handlers:
            print('handler {}'.format(handler))
            new_state = handler.act(driver, state, context)
            print('new_state {}, url {}'.format(new_state, driver.current_url))

            assert new_state is not None, "new_state is None"

            if new_state != state:
                return new_state

        return state

    def crawl(self, url, wait_response_seconds = 20):
        url = ShopCrawler.normalize_url(url)
        driver = ShopCrawler.create_driver()
        
        try:
            driver.implicitly_wait(wait_response_seconds)  # seconds
            driver.get(url)

            state = States.new
            new_state = state

            while state != States.purchased:
                frames = [None] + driver.find_elements_by_tag_name("iframe")

                for frame in frames:
                    with Frame(driver, frame):
                        new_state = self.process_state(driver, state)
                        if new_state != state:
                            break

                if state == new_state:
                    print("Didn't manage to finish site: {} stopped at state: {}, current url: {}"
                          .format(url, state, driver.current_url))

                    return False

                state = new_state

        finally:
            driver.quit()

        return True
