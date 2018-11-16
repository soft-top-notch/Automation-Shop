import logging
import traceback
from abc import abstractmethod
import requests
import selenium
import sys

sys.path.insert(0, '..')

from tracing.common_heuristics import *
from tracing.selenium_utils.common import *
from tracing.status import *


class States:
    new = "new"
    shop = "shop"
    product_page = "product_page"
    product_in_cart = "product_in_cart"
    cart_page = "cart_page"
    checkout_page = "checkout_page"
    payment_page = "payment_page"
    purchased = "purchased"

    states = [new, shop, product_page, product_in_cart, cart_page, checkout_page, payment_page, purchased]


class TraceContext:
    def __init__(self, domain, user_info, payment_info, delaying_time, tracer):
        self.user_info = user_info
        self.payment_info = payment_info
        self.domain = domain
        self.tracer = tracer
        self.trace_logger = tracer._trace_logger
        self.trace = None
        self.state = None
        self.url = None
        self.delaying_time = delaying_time
        self.is_started = False

    @property
    def driver(self):
        return self.tracer._driver

    def on_started(self):
        assert not self.is_started, "Can't call on_started when is_started = True"
        self.is_started = True
        self.state = States.new
        self.url = get_url(self.driver)
    
        if self.trace_logger:
            self.trace = self.trace_logger.start_new(self.domain)
            self.log_step(None, 'started')
    
    def on_handler_finished(self, state, handler):
        if self.state != state or self.url != get_url(self.driver):
            self.state = state
            self.url = get_url(self.driver)
            self.log_step(str(handler))
    
    def on_finished(self, status):
        assert self.is_started, "Can't call on_finished when is_started = False"
        self.is_started = False
        
        if not self.trace_logger:
            return
        
        self.log_step(None, 'finished')
        
        self.trace_logger.save(self.trace, status)
        self.trace = None
    
    def log_step(self, handler, additional = None):
        if not self.trace:
            return
        
        self.trace.save_snapshot(self.driver, self.state, handler, additional)


class IStepActor:

    def __init__(self):
        pass

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


class ShopTracer:
    def __init__(self,
                 get_user_data,
                 chrome_path='/usr/bin/chromedriver',
                 headless=False,
                 # Must be an instance of ITraceSaver
                 trace_logger = None
                 ):
        """
        :param get_user_data: Function that should return tuple (user_data.UserInfo, user_data.PaymentInfo)
            to fill checkout page
        :param chrome_path:   Path to chrome driver
        :param headless:      Wheather to start driver in headless mode
        :param trace_logger:  ITraceLogger instance that could store snapshots and source code during tracing
        """
        self._handlers = []
        self._get_user_data = get_user_data
        self._chrome_path = chrome_path
        self._logger = logging.getLogger('shop_tracer')
        self._headless = headless
        self._driver = None
        self._trace_logger = trace_logger

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
                return RequestError(code)
            
            return None
        
        except selenium.common.exceptions.TimeoutException:
            return Timeout(timeout)
            
        except requests.exceptions.ConnectionError:
            return NotAvailable(url)

    def get_driver(self, timeout=60):
        if self._driver:
            self._driver.quit()

        driver = create_chrome_driver(self._chrome_path, self._headless)
        driver.set_page_load_timeout(timeout)

        self._driver = driver

        return driver

    def process_state(self, driver, state, context):
        # Close popups if appeared
        close_alert_if_appeared(self._driver)

        handlers = [(priority, handler) for priority, handler in self._handlers
                    if handler.can_handle(driver, state, context)]

        handlers.sort(key=lambda p: -p[0])

        self._logger.info('processing state: {}'.format(state))

        for priority, handler in handlers:
            frames = get_frames(driver)
                
            if len(frames) > 1 and state == States.new:
                self._logger.info('found {} frames'.format(len(frames) - 1))

            frames_number = len(frames)
            for i in range(frames_number):
                if len(frames) > 1 and is_stale(frames[-1]):
                    frames = get_frames(driver)

                if len(frames) <= i:
                    break

                frame = frames[i]

                with Frame(driver, frame):
                    self._logger.info('handler {}'.format(handler))
                    new_state = handler.act(driver, state, context)
                    close_alert_if_appeared(self._driver)
                    self._logger.info('new_state {}, url {}'.format(new_state, get_url(driver)))

                    assert new_state is not None, "new_state is None"

                    context.on_handler_finished(new_state, handler)            

                    if new_state != state:
                        return new_state

        return state

    def trace(self, domain, wait_response_seconds = 60, attempts = 3, delaying_time = 10):
        """
        Traces shop
        :param domain:                 Shop domain to trace
        :param wait_response_seconds:  Seconds to wait response from shop
        :param attempts:               Number of attempts to navigate to checkout page
        :return:                       ITracingStatus
        """

        result = None
        best_state_idx = -1
        for _ in range(attempts):
            attempt_result = self.do_trace(domain, wait_response_seconds, delaying_time)

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

    def do_trace(self, domain, wait_response_seconds = 60, delaying_time = 10):

        url = ShopTracer.normalize_url(domain)

        driver = self.get_driver()
        state = States.new

        user_info, payment_info = self._get_user_data()

        context = TraceContext(domain, user_info, payment_info, delaying_time, self)
            
        try:
            status = ShopTracer.get(driver, url, wait_response_seconds)
            
            if status:
                return status

            context.on_started()   
            assert context.is_started
            
            if is_domain_for_sale(driver, domain):
                return NotAvailable('Domain {} for sale'.format(domain))

            new_state = state

            while state != States.purchased:
                new_state = self.process_state(driver, state, context)

                if state == new_state:
                    break

                state = new_state
                
        except:
            self._logger.exception("Unexpected exception during processing {}".format(url))
            exception = traceback.format_exc()
            status = ProcessingStatus(state, exception)
        
        finally:
            if not status:
                status = ProcessingStatus(state)
            
            if context.is_started:
                context.on_finished(status)

        return status