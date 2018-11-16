import logging
import traceback
import requests
import user_data
import selenium

from rl.environment import *
from abc import ABCMeta, abstractmethod
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
    checkoutLoginPage = "checkout_login_page"
    fillCheckoutPage = "fill_checkout_page"
    paymentMultipleSteps = "payment_multiple_steps"
    fillPaymentPage = "fill_payment_page"
    pay = "pay"

    states = [
        new, shop, product_in_cart, cart_page, product_page, 
        checkout_page, checkoutLoginPage, fillCheckoutPage, 
        paymentMultipleSteps, fillPaymentPage, pay, purchased
    ]


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
        return self.tracer.environment.driver

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


class IEnvActor:

    @abstractmethod
    def get_states(self):
        """
        States for actor
        """
        raise NotImplementedError

    @abstractmethod
    def filter_page(self, driver, state, context):
        return True

    @abstractmethod
    def get_action(self, control):
        """
        Should return an action for every control
        """
        raise NotImplementedError

    @abstractmethod
    def get_state_after_action(self, is_success, state, control, environment):
        """
        Should return a new state or the old state
        Also should return wheather environmenet should discard last action
        """
        raise NotImplementedError
    
    def can_handle(self, driver, state, context):
        states = self.get_states()

        if states and state not in states:
            return False

        return self.filter_page(driver, state, context)


class ISiteActor:

    @abstractmethod
    def get_states(self):
        """
        States for actor
        """
        raise NotImplementedError

    @abstractmethod
    def filter_page(self, driver, state, context):
        return True

    @abstractmethod
    def get_action(self, environment):
        """
        Should return an action for whole site
        """
        raise NotImplementedError

    @abstractmethod
    def get_state_after_action(self, is_success, state, environment):
        """
        Should return a new state or the old state
        Also should return wheather environmenet should discard last action
        """
        raise NotImplementedError
    
    def can_handle(self, driver, state, context):
        states = self.get_states()

        if states and state not in states:
            return False

        return self.filter_page(driver, state, context)


class ShopTracer:
    def __init__(self,
                 environment,
                 chrome_path='/usr/bin/chromedriver',
                 # Must be an instance of ITraceSaver
                 trace_logger = None,
                 ):
        """
        :param get_user_data: Function that should return tuple (user_data.UserInfo, user_data.PaymentInfo)
            to fill checkout page
        :param chrome_path:   Path to chrome driver
        :param headless:      Wheather to start driver in headless mode
        :param trace_logger:  ITraceLogger instance that could store snapshots and source code during tracing
        """
        self._handlers = []
        self._get_user_data = environment.user
        self._chrome_path = chrome_path
        self._logger = logging.getLogger('shop_tracer')
        self._headless = environment.headless
        self._trace_logger = trace_logger
        self.environment = environment

    def __enter__(self):
        pass
    
    def __exit__(self, type, value, traceback):
        self.environment.__exit__(type, value, traceback)

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
    
    def apply_actor(self, actor, state):
        if actor.__class__.__name__ == "SearchForProductPage":
            action = actor.get_action(self.environment)
            is_success,_ = self.environment.apply_action(None, action)
            new_state = actor.get_state_after_action(is_success, state, self.environment)

            if new_state != state:
                return new_state
        else:
            while self.environment.has_next_control():
                ctrl = self.environment.get_next_control()
                print(ctrl)
                action = actor.get_action(ctrl)
                print(action)
                if action.__class__.__name__ == "Nothing":
                    continue
                is_success,_ = self.environment.apply_action(ctrl, action)

                if is_success:
                    try:
                        current_state = (
                             get_url(self.environment.driver),
                            self.environment.c_idx,
                            self.environment.f_idx
                        )
                    except:
                        current_state = None
                    self.environment.states.append(current_state)
                new_state, discard = actor.get_state_after_action(is_success, state, ctrl, self.environment)

                # Discard last action
                if discard:
                    self.environment.discard()
                    
                if new_state != state:
                    return new_state        
        return state

    def process_state(self, state, context):
        # Close popups if appeared
        close_alert_if_appeared(self.environment.driver)

        handlers = [(priority, handler) for priority, handler in self._handlers
                    if handler.can_handle(self.environment.driver, state, context)]

        handlers.sort(key=lambda p: -p[0])

        self._logger.info('processing state: {}'.format(state))
        print(self._handlers)
        print(handlers)

        for priority, handler in handlers:
            self.environment.reset_control()
            self._logger.info('handler {}'.format(handler))
            new_state = self.apply_actor(handler, state)

            self._logger.info('new_state {}, url {}'.format(new_state, get_url(self.environment.driver)))
            assert new_state is not None, "new_state is None"

            if new_state != state:
                return new_state
        return state

    def trace(self, domain, wait_response_seconds = 60, attempts = 3, delaying_time = 10):
        """
        Traces shop

        :param domain:                 Shop domain to trace
        :param wait_response_seconds:  Seconds to wait response from shop
        :param attempts:               Number of attempts to navigate to checkout page
        :return:                       ICrawlingStatus
        """

        result = None
        best_state_idx = -1
        time_to_sleep = 2

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
            time.sleep(time_to_sleep)
            time_to_sleep = 2 * time_to_sleep
        return result

    def do_trace(self, domain, wait_response_seconds = 60, delaying_time = 10):
        state = States.new
        user_info, payment_info = self._get_user_data

        context = TraceContext(domain, user_info, payment_info, delaying_time, self)
            
        try:
            print("*** 1 ***")
            status = None

            if not self.environment.start(domain):
                return "Error is occured in starting environment"
            
            context.on_started()   
            assert context.is_started
            
            if is_domain_for_sale(self.environment.driver, domain):
                return NotAvailable('Domain {} for sale'.format(domain))

            new_state = state
            print("*** 2 ***")
            print(state)
            print(States.purchased)
            while state != States.purchased:
                print("*** 2.1 ***")
                new_state = self.process_state(state, context)

                if state == new_state:
                    break

                state = new_state
                
        except:
            print("*** 3 ***")
            self._logger.exception("Unexpected exception during processing {}".format(domain))
            exception = traceback.format_exc()
            status = ProcessingStatus(state, exception)

        finally:
            print("*** 4 ***")
            if not status:
                status = ProcessingStatus(state)
            
            if context.is_started:
                context.on_finished(status)

        return status
