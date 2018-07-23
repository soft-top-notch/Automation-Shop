import logging
import traceback
from abc import ABCMeta, abstractmethod
import requests
import selenium
from common_heuristics import *
from selenium_helper import *
from status import *


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


class UserInfo:
    def __init__(self,
                 first_name,
                 last_name,
                 company_name,
                 home,
                 street,
                 zip,
                 city,
                 state,
                 country,
                 phone,
                 email,
                 password
                 ):
        self.first_name = first_name
        self.company_name = company_name
        self.last_name = last_name
        self.home = home
        self.street = street
        self.zip = zip
        self.state = state
        self.city = city
        self.country = country
        self.phone = phone
        self.email = email
        self.password = password

    def get_json_userinfo(self):
        return {
            "first name": self.first_name,
            "last name": self.last_name,
            "country": self.country,
            "state": self.state,
            "home": self.home,
            "street": self.street,
            "zip": self.zip,
            "city": self.city,
            "phone": self.phone,
            "email": self.email,
            "password": self.password,
            "company": self.company_name
        }


class PaymentInfo:
    def __init__(self,
                 card_number,
                 card_name,
                 card_type,
                 expire_date_year,
                 expire_date_month,
                 cvc
                 ):
        self.card_number = card_number
        self.card_name = card_name
        self.card_type = card_type
        self.expire_date_year = expire_date_year
        self.expire_date_month = expire_date_month
        self.cvc = cvc

    def get_json_paymentinfo(self):
        return {
            "number": self.card_number,
            "name": self.card_name,
            "type": self.card_type,
            "expdate": str(self.expire_date_month) + str(self.expire_date_year)[:-2],
            "cvc": self.cvc,
        }


class TraceContext:
    def __init__(self, domain, user_info, payment_info, crawler):
        self.user_info = user_info
        self.payment_info = payment_info
        self.domain = domain
        self.crawler = crawler
        self.trace_logger = crawler._trace_logger
        self.trace = None
        
    def on_started(self):
        self.state = States.new
        self.url = self.crawler._driver.current_url
    
        if self.trace_logger:
            self.trace = self.trace_logger.start_new(self.domain)
            self.log_step(None, 'started')
    
    def on_handler_finished(self, state, handler):
        if self.state != state or self.url != self.crawler._driver.current_url:
            self.state = state
            self.url = self.crawler._driver.current_url
            self.log_step(handler)
    
    def on_finished(self, status):
        if not self.trace_logger:
            return
        
        self.log_step(None, 'finished')
        
        self.trace_logger.save(self.trace, status)
        self.trace = None
    
    def log_step(self, handler, additional = None):
        if not self.trace:
            return
        
        driver = self.crawler._driver
        self.trace.save_snapshot(driver, self.state, handler, additional)


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
    def __init__(self, 
                 user_info, 
                 payment_info,
                 chrome_path='/usr/local/chromedriver',
                 headless=False,
                 # Must be an instance of ITraceSaver
                 trace_logger = None
                 ):
        self._handlers = []
        self._analyzer = None
        self._user_info = user_info
        self._payment_info = payment_info
        self._chrome_path = chrome_path
        self._logger = logging.getLogger('shop_crawler')
        self._headless = headless
        self._driver = None
        self._trace_logger = trace_logger
        
        
    def __enter__(self):
        pass
    
    def __exit__(self, type, value, traceback):
        if self._driver:
            self._driver.quit()

    def init_analyzer(self, analyzer):
        self._analyzer = analyzer

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
                return RequestError(code)
            
            return None
        
        except selenium.common.exceptions.TimeoutException:
            return Timeout(timeout)
            
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

        if state == States.checkout_page:
            if not handlers:
                self._analyzer.save_urls(context.domain, False)
            else:
                self._analyzer.save_urls(context.domain, True)

        handlers.sort(key=lambda p: -p[0])

        self._logger.info('processing state: {}'.format(state))

        for priority, handler in handlers:
            self._logger.info('handler {}'.format(handler))
            new_state = handler.act(driver, state, context)
            self.close_popus_if_appeared()
            self._logger.info('new_state {}, url {}'.format(new_state, driver.current_url))

            assert new_state is not None, "new_state is None"
            
            context.on_handler_finished(new_state, handler)            

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
        for _ in range(attempts):
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

        driver = self.get_driver()
        state = States.new

        context = TraceContext(domain, self._user_info, self._payment_info, self)
            
        try:
            status = ShopCrawler.get(driver, url, wait_response_seconds)
            
            context.on_started()
            
            if status:
                return status

            if is_domain_for_sale(driver, domain):
                return NotAvailable(message = 'Domain {} for sale'.format(domain))

            new_state = state

            while state != States.purchased:
                frames = get_frames(driver)

                if len(frames) > 1:
                    self._logger.info('found {} frames'.format(len(frames) - 1))

                last_url = driver.current_url
                
                frames_number = len(frames)
                for i in range(frames_number):
                    if len(frames) > 1 and is_stale(frames[-1]):
                        frames = get_frames(driver)
                    
                    if len(frames) <= i:
                        break
                        
                    frame = frames[i]
                    
                    with Frame(driver, frame):
                        new_state = self.process_state(driver, state, context)
                        if new_state != state or last_url != driver.current_url:
                            break

                if state == new_state:
                    break
                    
                state = new_state
                
        except:
            self._logger.exception("Unexpected exception during processing {}".format(url))
            exception = traceback.format_exc()
            status = ProcessingStatus(state, exception=exception)
        
        finally:
            if not status:
                status = ProcessingStatus(state)
            
            context.on_finished(status)

        return status
