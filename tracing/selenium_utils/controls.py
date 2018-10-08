import logging
import pkg_resources as res

from tracing.selenium_utils.common import *


class Types:
    text = "text"
    select = "select"
    radiobutton = "radiobutton"
    checkbox = "checkbox"
    link = "link"
    button = "button"

    all_types = [text, select, radiobutton, checkbox, link, button]


def get_size(elem):
    driver = elem.parent
    
    s = elem.size
    # Naive check so far
    if elem.tag_name == 'a' or elem.tag_name == 'span':
        children = driver.execute_script('return arguments[0].children', elem)
        if len(children) == 1:
            child_size = children[0].size
            s['width'] = max(child_size['width'], s['width'])
            s['height'] = max(child_size['height'], s['height'])
    
    return s


def get_location(elem):
    driver = elem.parent
    
    loc = elem.location
    # Naive check so far
    if elem.tag_name == 'a' or elem.tag_name == 'span':
        children = driver.execute_script('return arguments[0].children', elem)
        children = list(filter(lambda x: x.is_displayed(), children))
        if len(children) == 1:
            child_loc = children[0].location
            loc['x'] = min(child_loc['x'], loc['x'])
            loc['y'] = min(child_loc['y'], loc['y'])
    
    return loc

class Control:
    def __init__(self, 
                 type, 
                 elem, 
                 label = None, 
                 values = None, 
                 min=None, 
                 max=None, 
                 code=None, 
                 label_elem = None,
                 tooltip = None
               ):
        self.type = type
        self.elem = elem
        self.label = label
        self.values = values
        self.min = min
        self.max = max
        self.code = code
        self.label_elem = label_elem
        self.tooltip = tooltip

        if self.label_elem and not self.label_elem.is_displayed():
            self.label_elem = None

    @staticmethod
    def get_right_bottom(elem):
       size = get_size(elem)
       loc = get_location(elem)
        
        # right bottom location
       return {'x': loc['x'] + size['width'], 
             'y': loc['y'] + size['height']}
        

    @property
    def location(self):
        loc = get_location(self.elem)
        if self.label_elem:
            loc_2 = get_location(self.label_elem)
            loc['x'] = min(loc['x'], loc_2['x'])
            loc['y'] = min(loc['y'], loc_2['y'])
        
        return loc

    @property
    def size(self):
        rb = Control.get_right_bottom(self.elem)
        if self.label_elem:
            rb2 = Control.get_right_bottom(self.label_elem)
            rb['x'] = max(rb['x'], rb2['x'])
            rb['y'] = max(rb['y'], rb2['y'])
 
        lt = self.location
        return {'width': rb['x'] - lt['x'],
                'height': rb['y'] - lt['y']}
        
    def get_center(self):
        return (self.location['x'] + self.size['width'] // 2, 
                self.location['y'] + self.size['height'] // 2)

   
    def __str__(self):
        return "Control: {}, label: {}, values: {}, min: {}, max = {}".format(
            self.type, self.label, self.values, self.min, self.max
        )

    def str_values(self):
        return ','.join(self.values or [])

    def __hash__(self):
        return (hash(self.type) ^
                hash(self.location['x']) ^
                hash(self.location['y']) ^
                hash(self.size['width']) ^
                hash(self.size['height']) ^
                hash(self.str_values()) ^
                hash(self.label or '')
              )

    def __eq__(self, other):
        return (
                self.__class__ == other.__class__ and
                self.type == other.type and
                (self.values or []) == (other.values or []) and
                self.location == other.location and 
                self.size == other.size and
                (self.label or '') ==( other.label or '')
               )

    @staticmethod
    def create_select(element):
        driver = element.parent
        label, label_elem = get_label_with_elem(element)

        values = extract_combobox_values(driver, element)
        return Control(Types.select, element, label, values, label_elem = label_elem)

    @staticmethod
    def create_input(element):
        label, label_elem = get_label_with_elem(element)

        return Control(Types.text, element, label, label_elem = label_elem)

    @staticmethod
    def create_button(element):
        text = element.get_attribute("innerText") or element.get_attribute('value')
        tooltip = element.get_attribute('tooltip') or element.get_attribute('titile')

        return Control(Types.button, element, text, tooltip = tooltip)

    @staticmethod
    def create_link(element):
        text = element.get_attribute("innerText")
        tooltip = element.get_attribute('tooltip') or element.get_attribute('titile')

        return Control(Types.link, element, text, code = element.get_attribute('href'), tooltip = tooltip)

    @staticmethod
    def create_checkbox(element):
        label, label_elem = get_label_with_elem(element)

        return Control(Types.checkbox, element, label, label_elem = label_elem)

    @staticmethod
    def create_radiobutton(element):
        label, label_elem = get_label_with_elem(element)

        return Control(Types.radiobutton, element, label, label_elem = label_elem)


def is_js_function_exists(driver, function):
    """
    Detects if js function is defined in the current Web Driver Page
    :param driver:    Web driver
    :param function:  Javascript function
    :return:          If function is defined
    """
    return driver.execute_script('return typeof {} === "function"'.format(function))


def add_scripts_if_need(driver, file='js/selenium.js', function_to_check = "__tra_sleep", resource=True):
    """
    Adds javascript file to current page
    :param driver:             Web driver
    :param file:               Path to local js file to add
    :param function_to_check:  Function to check weather file has already been added
    :param resource:           Is file located in tracing package resources
    """
    if function_to_check is not None and is_js_function_exists(driver, function_to_check):
        return

    if resource:
        file = res.resource_filename('tracing', file)

    with open(file) as f:
        script = '\n'.join([line for line in f])
        driver.execute_script(script)


def execute_async(driver, script):
    """
    Executes script async returning value from callback continuation
    :param driver:   Web driver
    :param script:   Script that defines Promise
    :return:         Value after waiting for Promise result
    """
    full_script = "done = arguments[0];" + \
                  script + ".then(result => {done(result)})"

    return driver.execute_async_script(full_script)


def scroll_to_element(driver, element):
    last_scroll = driver.execute_script('return Math.max(document.documentElement.scrollTop, document.body.scrollTop);')
    # location could change during scrolling do it until it fixed
    for i in range(5):
        y = element.location['y']
        scroll_to(driver, max(0, y - 200))
        scroll = driver.execute_script('return Math.max(document.documentElement.scrollTop, document.body.scrollTop);')
        if last_scroll == scroll:
            break
        
    return (element.location['x'], element.location['y'] - scroll)
    

def extract_combobox_values(driver, element):
    """
    Extracts combobox values by it's location
    :param driver: Web driver
    :param left:   Left coordinate of the combobox
    :param top:    Top coordinate of the combobox
    :param height: Height of the combobox
    :return:       List of texts of values that could be selected from the combobox
    """
    add_scripts_if_need(driver)
    
    left, top = scroll_to_element(driver, element)
    height = element.size['height']
    width = element.size['width']

    script =  '__tra_extractComboValues({},{},{},{})'.format(left, top, width, height)
    return execute_async(driver, script)


def select_combobox_value(driver, element, value_text):
    """
    Selects combobox value
    :param driver:     Web driver
    :param left:       Left coordinate of the combobox
    :param top:        Right coordinate of the combobox
    :param height:     Height of the combobox
    :param value_text: Text of value to select
    :return:           Weather select is success or not
    """
    add_scripts_if_need(driver)
    
    left, top = scroll_to_element(driver, element)
    height = element.size['height']
    width = element.size['width']
    return execute_async(driver, "__tra_selectComboboxValue({},{},{},{},'{}')".format(left, top, width, height, value_text))


def click(driver, elem):
    """
    Clicks at point in the page
    :param driver:  Web driver
    :param x:       Left of the page
    :param y:       Top of the page
    """

    add_scripts_if_need(driver)
    
    x, y = scroll_to_element(driver, elem)
    height = elem.size['height']
    width = elem.size['width']

    assert height > 1 and width > 1, "element must have at least 2 pixels width and height"

    driver.execute_script('el = document.elementFromPoint({}, {}); __tra_simulateClick(el);'.format(x + width//2, y + height//2))


def enter_text(driver, elem, text):
    """
    Enters text to text field
    :param driver:   Web driver
    :param x:        Left for any point of the text field
    :param y:        Top for any point of the text field
    :param text:     Text to input
    """
    add_scripts_if_need(driver)
    
    x, y = scroll_to_element(driver, elem)
    height = elem.size['height']
    width = elem.size['width']
    assert height > 1 and width > 1, "element must have at least 2 pixels width and height"

    driver.execute_script('el = document.elementFromPoint({}, {}); el.value = "{}";'.format(x + width//2, y + height//2, text))


def is_visible(elem):
    """
    Detects whether elem is visible or not
    :param elem:    WebElement
    :return:        True if visible and False otherwise
    """
    driver = elem.parent
    if is_stale(elem):
        return False

    if elem.size['width'] <= 1 or elem.size['height'] <= 1:
        return False
    
    if elem.size['width'] + elem.location['x'] <= 0:
        return False

    if elem.size['height'] + elem.location['y'] <= 0:
        return False

    x, y = scroll_to_element(driver, elem)

    x = x + elem.size['width'] // 2
    y = y + elem.size['height'] // 2
    
    html = driver.execute_script('el=document.elementFromPoint({}, {});return el ? el.outerHTML:"";'.format(x, y))
    return len(html) > 0 and html in elem.get_attribute('outerHTML')


def get_label_with_elem(element):
    """
    Extracts element label
    :param element:      WebElement
    :return:             Tuple: (Label, Label element)
    """
    driver = element.parent
    id = element.get_attribute("id")
    if id:
        labels = driver.find_elements_by_css_selector('label[for="{}"]'.format(id))
        if labels:
            return (labels[0].get_attribute("innerText"), labels[0])

    parent = element.find_element_by_xpath('..')
    if parent and parent.tag_name == "label":
        return (parent.get_attribute("innerText"), parent)

    placeholder = element.get_attribute('placeholder')
    if placeholder:
        return (placeholder, element)

    
    if len(parent.find_elements_by_css_selector("*")) == 1:
        return (parent.get_attribute("innerText"), parent)

    return (None, element)


def get_label(element):
    """
    Extracts element label
    :param element:      WebElement
    :return_label_elem:  if True then returns tuple (label, label_elem)
    :return:             String Label if label found
    """
    label, _ = get_label_with_elem(element)
    
    return label

def get_checkboxes(driver):
    return driver.find_elements_by_css_selector("input[type='checkbox']")


def get_radiobuttons(driver):
    return driver.find_elements_by_css_selector("input[type='radio']")


def get_selects(driver):
    # Add at least two heuristic based
    return driver.find_elements_by_tag_name('select')


def get_inputs(driver):
    inputs = driver.find_elements_by_css_selector('input[type="text"]')
    searches = driver.find_elements_by_css_selector('input[type="search"]')
    nums = driver.find_elements_by_css_selector('input[type="num"]')
    tels = driver.find_elements_by_css_selector('input[type="tel"]')
    emails = driver.find_elements_by_css_selector('input[type="email"]')
    urls = driver.find_elements_by_css_selector('input[type="url"]')

    texts = driver.find_elements_by_tag_name('textarea')

    return inputs + searches + texts + nums + tels + emails + urls


def get_checkboxes(driver):
    return driver.find_elements_by_css_selector('input[type="checkbox"]')


def gather_click_elements(driver):
    add_scripts_if_need(driver)
    return driver.execute_script('return __tra_gatherClickElements()')


def extract_controls(driver):
    frames = get_frames(driver)
    
    selects = [Control.create_select(elem) for elem in get_selects(driver)
       if is_visible(elem)]
    inputs = [Control.create_input(elem) for elem in get_inputs(driver) if is_visible(elem)]
    buttons = [Control.create_button(elem) for elem in get_buttons(driver) if is_visible(elem)]
    links = [Control.create_link(elem) for elem in get_links(driver) if is_visible(elem)]

    checkboxes = [Control.create_checkbox(elem) for elem in get_checkboxes(driver) if is_visible(elem)]
    radios = [Control.create_radiobutton(elem) for elem in get_radiobuttons(driver) if is_visible(elem)]

    others = [Control.create_button(elem) for elem in gather_click_elements(driver) if is_visible(elem)]
 
    controls = (selects + inputs + buttons + links + checkboxes + radios + others)
    
    return list(set(controls))


def normalize_url(url):
    if not url:
        return url

    return url[:url.index('#')] if '#' in url else url


def is_link(elem):
    try:
        driver = elem.parent
        href = elem.get_attribute('href')
        href = normalize_url(href)
        return href and not href.startswith('javascript:') and href != driver.current_url
    except:
        logger = logging.getLogger('shop_tracer')
        logger.debug('Unexpected exception during check if element is link {}'.format(traceback.format_exc()))
        return False


def get_links(driver):
    links = driver.find_elements_by_css_selector("a[href]")
    return [link for link in links if is_link(link)]


def get_buttons(driver):
    links = [elem for elem in driver.find_elements_by_tag_name("a") if not is_link(elem)]
    buttons = driver.find_elements_by_tag_name("button")
    inputs = driver.find_elements_by_css_selector('input[type="button"]')
    submits = driver.find_elements_by_css_selector('input[type="submit"]')
    imgs = driver.find_elements_by_css_selector('input[type="image"]')

    return links + buttons + inputs + submits + imgs
