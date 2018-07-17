from shop_crawler import *
from selenium_helper import *
import nlp
import random

from common_heuristics import *

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

from selenium.webdriver.support.ui import Select

import sys
import traceback
       

class ToProductPageLink(IStepActor):
    def get_states(self):
        return [States.new, States.shop]

    def find_to_product_links(self, driver):
        return find_links(driver, ['/product', '/commodity', '/drug', 'details', 'view'], by_path=False)

    @staticmethod
    def process_links(driver, state, links):
        if not links:
            return state
        
        attempts = 3
        links = list(links)
        random.shuffle(links)
        
        for i in range(attempts):
            if i >= len(links):
                break
                
            link = links[i]
            
            url = ShopCrawler.normalize_url(link)
            driver.get(url)
            time.sleep(5)
            
            # Check that have add to cart buttons
            if AddToCart.find_to_cart_elements(driver):
                return States.product_page
            else:
                back(driver)

        return state
    
    
    def process_page(self, driver, state, context):
        links = list([link.get_attribute('href') for link in self.find_to_product_links(driver)])
        return ToProductPageLink.process_links(driver, state, links)

    
class AddToCart(IStepActor):
    def get_states(self):
        return [States.new, States.shop, States.product_page]

    @staticmethod
    def find_to_cart_elements(driver):
        return find_buttons_or_links(driver, ["addtocart", 
                                              "addtobag", 
                                              "add to cart",
                                              "add to bag"], ['where'])
        
    def process_page(self, driver, state, context):
        elements = AddToCart.find_to_cart_elements(driver)
        
        if click_first(driver, elements, try_handle_popups, randomize = True):
            time.sleep(5)
            return States.product_in_cart
        else:
            return state


class ToShopLink(IStepActor):
    def get_states(self):
        return [States.new]

    def find_to_shop_elements(self, driver):
        return find_buttons_or_links(driver, ["shop", "store", "products"], ["shops", "stores", "shopping"])

    def process_page(self, driver, state, context):
        elements = self.find_to_shop_elements(driver)
        if click_first(driver, elements, try_handle_popups):
            return States.shop
        else:
            return state


class ToCartLink(IStepActor):
    def find_to_cart_links(self, driver):
        return find_links(driver, ["cart"], ['add', 'append'], by_path=False)

    def get_states(self):
        return [States.product_in_cart]

    def process_page(self, driver, state, context):
        
        attempts = 3
        for attempt in range(attempts):
            btns = self.find_to_cart_links(driver)

            if len(btns) <= attempt:
                break
                
            if click_first(driver, btns, randomize = True):
                time.sleep(5)
                checkouts = ToCheckout.find_checkout_elements(driver)
                
                if not is_empty_cart(driver) and len(checkouts) > 0:
                    return States.cart_page
                else:
                    back(driver)
             
        
        return state


class ToCheckout(IStepActor):

    @staticmethod
    def find_checkout_elements(driver):
        contains =  ["checkout", "check out"]
        not_contains = ['guest', 'continue shopping', 'return']
        btns = find_buttons_or_links(driver, contains, not_contains)
        
        # if there are buttongs that contains words in text return them first
        exact = []
        for btn in btns:
            text = btn.get_attribute('innerHTML')
            if nlp.check_text(text, contains, not_contains):
                exact.append(btn)
        
        if len(exact) > 0:
            return exact
        
        return btns
        
    def get_states(self):
        return [States.product_in_cart, States.cart_page]

    
    @staticmethod
    def has_checkout_btns(driver):
        btns = ToCheckout.find_checkout_elements(driver)
        return len(btns) > 0

    
    @staticmethod
    def process(driver, state, max_depth=3):
        btns = ToCheckout.find_checkout_elements(driver)

        if click_first(driver, btns):
            time.sleep(5)
            if not is_empty_cart(driver):
                if ToCheckout.has_checkout_btns(driver) and max_depth > 0:                    
                    ToCheckout.process(driver, state, max_depth - 1)
                
                return States.checkout_page
        
        return state
    
    def process_page(self, driver, state, context):
        return ToCheckout.process(driver, state)

    
class SearchForProductPage(IStepActor):
    
    def get_states(self):
        return [States.new, States.shop]
        
    def search_in_google(self, driver, query):
        driver.get('https://www.google.com')
        time.sleep(1)

        search_input = driver.find_element_by_css_selector('input.gsfi')
        search_input.clear()
        search_input.send_keys(query)
        search_input.send_keys(Keys.ENTER)
        time.sleep(2)

        links = driver.find_elements_by_css_selector('div.g .rc .r a[href]')
            
        if len(links) > 0:
            return [link.get_attribute("href") for link in links]
        else:
            return None

    
    def search_in_bing(self, driver, query):
        driver.get('https://www.bing.com')
        time.sleep(1)
        
        search_input = driver.find_element_by_css_selector('input.b_searchbox')
        search_input.clear()
        search_input.send_keys(query)
        search_input.send_keys(Keys.ENTER)
        time.sleep(2)
        
        links = driver.find_elements_by_css_selector('ol#b_results > li.b_algo > h2 > a[href]')
        
        if len(links) > 0:
            return [link.get_attribute("href") for link in links]
        else:
            return None
    
    def search_for_product_link(self, driver, domain):
        queries = ['"add to cart"']

        links = None
        # Open a new tab
        try:
            new_tab(driver)
            for query in queries:
                google_query = 'site:{} {}'.format(domain, query)

                searches = [self.search_in_bing, self.search_in_google]
                for search in searches:
                    try:
                        links = search(driver, google_query)
                        if links:
                            return links
                        
                    except:
                        logger = logging.getLogger('shop_crawler')
                        logger.exception('during search in search engine got an exception')

        finally:
            # Close new tab
            close_tab(driver)
        
        return links
    
    def process_page(self, driver, state, context):
        links = self.search_for_product_link(driver, context.domain)
        
        if links:
            return ToProductPageLink.process_links(driver, state, links)
        
        return state
    
       
def add_crawler_extensions(crawler):
    crawler.add_handler(AddToCart(), 4)
    crawler.add_handler(SearchForProductPage(), 1)
    crawler.add_handler(ToProductPageLink(), 3)
    crawler.add_handler(ToShopLink(), 2)

    crawler.add_handler(ToCheckout(), 3)
    crawler.add_handler(ToCartLink(), 2)
    
