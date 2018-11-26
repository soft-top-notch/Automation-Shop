import requests
import selenium
from abc import abstractmethod
from tracing.common_heuristics import *
from tracing.status import *
from tracing.rl.environment import Environment
from tracing.rl.actions import Nothing


class ITraceListener:

    def on_tracing_started(self, url):
        pass

    def before_action(self, environment, control = None, state = None):
        pass

    def after_action(self, action, is_success, new_state = None):
        pass

    def on_tracing_finished(self, status):
        pass


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
    prePaymentFillingPage = "pre_payment_filling_page"
    fillCheckoutPage = "fill_checkout_page"
    prePaymentFillingPage = "pre_payment_filling_page"
    fillPaymentPage = "fill_payment_page"
    pay = "pay"

    states = [
        new, shop, product_page, product_in_cart, cart_page,
        checkout_page, checkoutLoginPage, fillCheckoutPage,
        prePaymentFillingPage, fillPaymentPage, pay, purchased
    ]


class TraceContext:
    def __init__(self, domain, delaying_time, tracer):
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
    def __init__(self):
        pass

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
    def __init__(self):
        pass

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
                 trace_logger = None
                 ):
        """
        :param environment    Environment that wraps selenium

        :param chrome_path:   Path to chrome driver
        :param headless:      Wheather to start driver in headless mode
        :param trace_logger:  ITraceLogger instance that could store snapshots and source code during tracing
        """
        if environment is None:
            environment = Environment()

        self.environment = environment
        self._handlers = []
        self._chrome_path = chrome_path
        self._logger = logging.getLogger('shop_tracer')
        self._headless = environment.headless
        self._trace_logger = trace_logger

        self.action_listeners = []

    def __enter__(self):
        pass
    
    def __exit__(self, type, value, traceback):
        self.environment.__exit__(type, value, traceback)

    def add_listener(self, listener):
        self.action_listeners.append(listener)

    def on_tracing_started(self, url):
        for listener in self.action_listeners:
            listener.on_tracing_started(url)

    def on_before_action(self, control = None, state = None):
        for listener in self.action_listeners:
            listener.before_action(self.environment, control, state)

    def on_after_action(self, action, is_success, new_state = None):
        for listener in self.action_listeners:
            listener.after_action(action, is_success, new_state)

    def on_tracing_finished(self, status):
        for listener in self.action_listeners:
            listener.on_tracing_finished(status)

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

    def apply_actor(self, actor, state):
        if isinstance(actor, ISiteActor):
            self.on_before_action(state=state)

            action = actor.get_action(self.environment)
            self.environment.save_state()

            is_success,_ = self.environment.apply_action(None, action)
            new_state = actor.get_state_after_action(is_success, state, self.environment)

            if new_state != state:
                self.on_after_action(action, True, new_state = new_state)
                return new_state
            else:
                self.on_after_action(action, False, new_state = new_state)
                self.environment.discard()
        else:
            assert isinstance(actor, IEnvActor), "Actor {} must be IEnvActor".format(actor)

            while self.environment.has_next_control():
                ctrl = self.environment.get_next_control()
                self.on_before_action(ctrl, state = state)
                action = actor.get_action(ctrl)

                if not isinstance(action, Nothing):
                    self._logger.info(ctrl)
                    self._logger.info(action)
                    self.environment.save_state()

                is_success,_ = self.environment.apply_action(ctrl, action)
                is_success = is_success and not isinstance(action, Nothing)
                new_state, discard = actor.get_state_after_action(is_success, state, ctrl, self.environment)
                self.on_after_action(action, is_success and not discard, new_state=new_state)

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
            self.on_tracing_started(domain)
            attempt_result = self.do_trace(domain, wait_response_seconds, delaying_time)
            self.on_tracing_finished(attempt_result)

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

        context = TraceContext(domain, delaying_time, self)

        try:
            status = None

            if not self.environment.start(domain):
                return NotAvailable('Domain {} is not available'.format(domain))

            context.on_started()   
            assert context.is_started
            
            if is_domain_for_sale(self.environment.driver, domain):
                return NotAvailable('Domain {} for sale'.format(domain))

            while state != States.purchased:
                new_state = self.process_state(state, context)

                if state == new_state:
                    break

                state = new_state
                
        except:
            self._logger.exception("Unexpected exception during processing {}".format(domain))
            exception = traceback.format_exc()
            status = ProcessingStatus(state, exception)

        finally:
            if not status:
                status = ProcessingStatus(state)
            
            if context.is_started:
                context.on_finished(status)

        return status
