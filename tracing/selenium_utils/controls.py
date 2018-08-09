import logging


class Types:
    text = "text"
    select = "select"
    radiobutton = "radiobutton"
    checkbox = "checkbox"
    link = "link"
    button = "button"

    all_types = [text, select, radiobutton, checkbox, link, button]


class Control:
    def __init__(self, type, location, size, label = None, values = None, min=None, max=None, code=None):
        self.type = type
        self.location = location
        self.size = size
        self.label = label
        self.values = values
        self.min = min
        self.max = max
        self.code = code

    def __str__(self):
        return "Control: {}, location: {}, size: {}, label: {}, values: {}, min: {}, max = {}".format(
            self.type, self.location, self.size, self.label, self.values, self.min, self.max
        )

    def __hash__(self):
        return (hash(self.type) ^
                hash(self.location['x']) ^
                hash(self.location['y']) ^
                hash(self.size['width']) ^
                hash(self.size['height']))

    def __eq__(self, other):
        return (
                self.__class__ == other.__class__ and
                self.type == other.type and
                self.location['x'] == other.location['x'] and
                self.location['y'] == other.location['y'] and
                self.size['width'] == other.size['width'] and
                self.size['height'] == other.size['height'])

    @staticmethod
    def create_select(element):
        driver = element.parent
        loc = element.location
        size = element.size
        label = get_label(element)

        values = extract_combobox_values(driver, loc['x'], loc['y'], size['width'], size['height'])
        return Control(Types.select, loc, size, label, values)

    @staticmethod
    def create_input(element):
        loc = element.location
        size = element.size
        label = get_label(element)

        return Control(Types.text, loc, size, label)

    @staticmethod
    def create_button(element):
        loc = element.location
        size = element.size
        text = element.get_attribute("innerText") or element.get_attribute('value')

        return Control(Types.button, loc, size, text)

    @staticmethod
    def create_link(element):
        loc = element.location
        size = element.size
        text = element.get_attribute("innerText")

        return Control(Types.link, loc, size, text, code = element.get_attribute('href'))

    @staticmethod
    def create_checkbox(element):
        loc = element.location
        size = element.size
        label = get_label(element)

        return Control(Types.checkbox, loc, size, label)

    @staticmethod
    def create_radiobutton(element):
        loc = element.location
        size = element.size
        label = get_label(element)

        return Control(Types.radiobutton, loc, size, label)


def is_js_function_exists(driver, function):
    """
    Detects if js function is defined in the current Web Driver Page
    :param driver:    Web driver
    :param function:  Javascript function
    :return:          If function is defined
    """
    return driver.execute_script('return typeof {} === "function"'.format(function))


def add_scripts_if_need(driver, file='js/selenium.js', function_to_check = "__tra_sleep"):
    """
    Adds javascript file to current page
    :param driver:             Web driver
    :param file:               Path to local js file to add
    :param function_to_check:  Function to check weather file has already been added
    """
    if function_to_check is not None and is_js_function_exists(driver, function_to_check):
        return

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


def extract_combobox_values(driver, left, top, width, height):
    """
    Extracts combobox values by it's location
    :param driver: Web driver
    :param left:   Left coordinate of the combobox
    :param top:    Top coordinate of the combobox
    :param height: Height of the combobox
    :return:       List of texts of values that could be selected from the combobox
    """
    add_scripts_if_need(driver)

    script =  '__tra_extractComboValues({},{},{})'.format(left + width // 2, top, height)
    return execute_async(driver, script)


def select_combobox_value(driver, left, top, height, value_text):
    """
    Selects combobox value
    :param driver:     Web driver
    :param left:       Left coordinate of the combobox
    :param top:        Right coordinate of the combobox
    :param height:     Height of the combobox
    :param value_text: Text of value to select
    :return:           Weather select is success or not
    """
    return execute_async(driver, "__tra_selectComboboxValue({},{},{},'{}')".format(left, top, height, value_text))


def is_visible(elem):
    """
    Detects whether elem is visible or not
    :param elem:    WebElement
    :return:        True if visible and False otherwise
    """
    driver = elem.parent

    loc = elem.location
    size = elem.size

    if size['width'] <= 1 or size['height'] <= 1:
        return False

    x = loc['x'] + size['width'] // 2
    y = loc['y'] + size['height'] // 2

    html = driver.execute_script('el=document.elementFromPoint({}, {});return el ? el.outerHTML:"";'.format(x, y))
    return len(html) > 0 and html in elem.get_attribute('outerHTML')


def get_label(element):
    """
    Extracts element label
    :param element:   WebElement
    :return:          String Label if label found
    """
    driver = element.parent
    id = element.get_attribute("id")
    if id:
        labels = driver.find_elements_by_css_selector('label[for="{}"]'.format(id))
        if labels:
            return labels[0].get_attribute("innerText")

    parent = element.find_element_by_xpath('..')
    if parent and parent.tag_name == "label":
        return parent.get_attribute("innerText")

    return element.get_attribute('placeholder')


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
    selects = [Control.create_select(elem) for elem in get_selects(driver)
               if is_visible(elem)]
    inputs = [Control.create_input(elem) for elem in get_inputs(driver) if is_visible(elem)]
    buttons = [Control.create_button(elem) for elem in get_buttons(driver) if is_visible(elem)]
    links = [Control.create_link(elem) for elem in get_links(driver) if is_visible(elem)]

    checkboxes = [Control.create_checkbox(elem) for elem in get_checkboxes(driver) if is_visible(elem)]
    radios = [Control.create_radiobutton(elem) for elem in get_radiobuttons(driver) if is_visible(elem)]

    others = [Control.create_button(elem) for elem in gather_click_elements(driver) if is_visible(elem)]

    controls = selects + inputs + buttons + links + checkboxes + radios + others
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