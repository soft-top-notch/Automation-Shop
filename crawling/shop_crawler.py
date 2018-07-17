import logging
import traceback
from abc import ABCMeta, abstractmethod
from selenium import webdriver
import sys
import time
from selenium.webdriver.common.keys import Keys
from selenium_helper import *
import requests
import selenium
import nlp
from common_heuristics import *

from selenium.webdriver.support.expected_conditions import staleness_of


class States:
    new = "new"
    shop = "shop"
    product_page = "product_page"
    product_in_cart = "product_in_cart"
    cart_page = "cart_page"
    checkout_page = "checkout_page"
    payment_page = "payment_page"
    purchased = "purchased"

    states = [new, shop, product_page, product_in_cart, checkout_page, payment_page, purchased]

    
class ICrawlingStatus:
    """
        Status of Shop crawling
    """
    def __init__(self, 
                 url, 
                 status, 
                 message = None, 
                 limit = 60, 
                 redirected_to_domain = None, 
                 state = None,
                 exception = None,
                 chain_urls = None
                ):
        
        self.url = url
        self.status = status
        self.message = message
        self.limit = limit
        self.redirected_to_domain = redirected_to_domain
        self.state = state
        self.exception = exception,
        self.chain_urls = chain_urls
        
    def __str__(self):
        if self.message:
            return 'Status: "{}" after processing url "{}"\n {}'.format(self.status, self.url, self.message)
        else:
            return 'Status: "{}" after processing url "{}"'.format(self.status, self.url)
            

class NotAvailable(ICrawlingStatus):
    """
        Status for shop that are not available
    """
    def __init__(self, url, message = None):
        super().__init__(url, 'Not Available', message = message)

class RequestError(ICrawlingStatus):
    """
        Get response with ant
    """
    def __init__(self, url, code, message = None):
        self.code = code
        super().__init__(url, 'Error {}'.format(self.code), message = message)

class Timeout(ICrawlingStatus):
    def __init__(self, url, limit, message = None):
        super().__init__(url, "Time Out", message = message)
        self.limit = limit
        
class ProcessingStatus(ICrawlingStatus):
    def __init__(self, url, chain_urls, state, exception = None, message = None):
        super().__init__(url, 'Processing Finished at State',
                         state = state, 
                         exception = exception, 
                         chain_urls = chain_urls,
                         message = message
                        )


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
    def __init__(self, domain, user_info, payment_info):
        self.user_info = user_info
        self.payment_info = payment_info
        self.domain = domain


class IStepActor:

    @abstractmethod
    def filter_page(self, driver, state, context):
        return True

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
        self._logger = logging.getLogger('shop_crawler')
        self._headless = headless
        self._driver = None
        
        
    def __enter__(self):
        pass
    
    def __exit__(self, type, value, traceback):
        if self._driver:
            self._driver.quit()
            

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
    def get(driver, url, timeout=10):
        try:
            driver.get(url)
            response = requests.get(url, verify=False, timeout=timeout)
            code = response.status_code
            if code >= 400:
                return RequestError(url, code)
            
            return None
        
        except selenium.common.exceptions.TimeoutException:
            return Timeout(url, timeout)
            
        except requests.exceptions.ConnectionError:
            return NotAvailable(url)
    
    
    def close_popus_if_appeared(self):
        close_alert_if_appeared(self._driver)
        try_handle_popups(self._driver)    
            
        
    def get_driver(self, timeout=60):
        if self._driver:
            self._driver.quit()
            
        driver = create_chrome_driver(self._chrome_path, self._headless)
        driver.set_page_load_timeout(timeout)
        
        self._driver = driver
        
        return driver
    
    def process_state(self, driver, state, context):
        # Close popups if appeared
        self.close_popus_if_appeared()
            
        handlers = [(priority, handler) for priority, handler in self._handlers
                    if handler.can_handle(driver, state, context)]

        handlers.sort(key=lambda p: -p[0])

        self._logger.info('processing state: {}'.format(state))
        
        for priority, handler in handlers:
            self._logger.info('handler {}'.format(handler))
            new_state = handler.act(driver, state, context)
            self.close_popus_if_appeared()
            self._logger.info('new_state {}, url {}'.format(new_state, driver.current_url))

            assert new_state is not None, "new_state is None"

            if new_state != state:
                return new_state

        return state

    def crawl(self, domain, wait_response_seconds = 60, attempts = 3):
        """
            Crawls shop in domain
            Returns ICrawlingStatus
        """
        
        result = None
        best_state_idx = -1
        for attempt in range(attempts):
            attempt_result = self.do_crawl(domain, wait_response_seconds)
            
            if isinstance(attempt_result, ProcessingStatus):
                idx = States.states.index(attempt_result.state)
                if idx > best_state_idx:
                    best_state_idx = idx
                    result = attempt_result
                
                # Don't need randomization if we have already navigated to checkout page
                if idx >= States.states.index(States.checkout_page):
                    break
                
            if not result:
                result = attempt_result
                
        return result
    
    
    def do_crawl(self, domain, wait_response_seconds = 60):

        url = ShopCrawler.normalize_url(domain)
        chain_urls = [url]
        context = StepContext(domain, self._user_info, self._payment_info)

        driver = self.get_driver()
        state = States.new
        
        try:
            status = ShopCrawler.get(driver, url, wait_response_seconds)
            
            if status:
                return status
            
            if is_domain_for_sale(driver, domain):
                return NotAvailable(url, message = 'Domain {} for sale'.format(domain))
            
            new_state = state

            while state != States.purchased:
                frames = get_frames(driver)
                
                if driver.current_url != chain_urls[-1]:
                    chain_urls.append(driver.current_url)
                    
                if len(frames) > 1:
                    self._logger.info('found {} frames'.format(len(frames) - 1))
                   
                last_url = driver.current_url
                
                frames_number = len(frames)
                for i in range(frames_number):
                    if len(frames) > 1 and staleness_of(frames[-1]):
                        frames = get_frames(driver)
                    
                    if len(frames) <= i:
                        break
                        
                    frame = frames[i]
                    
                    with Frame(driver, frame):
                        new_state = self.process_state(driver, state, context)
                        if new_state != state or last_url != driver.current_url:
                            break
                
                if state == new_state:
                    return ProcessingStatus(domain, chain_urls, state)
                    
                state = new_state
        except:
            self._logger.exception("Unexpected exception during processing {}".format(url))
            exception = traceback.format_exc()
            return ProcessingStatus(domain, chain_urls, state, exception=exception)
            
        return ProcessingStatus(domain, chain_urls, state)
