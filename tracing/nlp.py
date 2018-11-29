import re

def normalize_text(text):
    # ToDo Proper normalization
    return text.lower()\
        .replace('-', ' ') \
        .replace('_', ' ') \
        .replace('  ', ' ')

def tokenize(text):
    return re.split(r'(\d+|\W+)', text)

def check_text(text, contains, not_contains=None, normalize=True):
    if not contains:
        contains = []

    if not not_contains:
        not_contains = []

    if normalize:
        text = normalize_text(text)

    has_searched = False
    for str in contains:
        if re.search(str, text):
            has_searched = True
            break

    if not has_searched and len(contains) > 0:
        return False

    has_forbidden = False
    for str in not_contains:
        if re.search(str, text):
            has_forbidden = True
            break

    return not has_forbidden


def check_text_with_label(value, contains, not_contains=None, normalize=True):
    text = value[0]
    label = value[1]

    if not contains:
        contains = []

    if not not_contains:
        not_contains = []

    if normalize:
        text = normalize_text(text)

    has_searched = False
    for str in contains:
        print (text, label)
        print (re.search(str, text), re.search(str, label), "............", str)
        if re.search(str, text):
            has_searched = True
            break
        elif re.search(str, label):
            has_searched = True
            break

    if not has_searched and len(contains) > 0:
        return False

    has_forbidden = False
    for str in not_contains:
        if re.search(str, text):
            has_forbidden = True
            break

    return not has_forbidden


def remove_letters(text, contains):
    strName = text
    for elem in contains:
        strName=strName.replace(elem, "")
    return strName


def check_if_empty_cart(text):
    contains = ['(cart|bag) (\w+ |)is empty',
                '(cart|bag) is (\w+ |)empty',
            'zero (products|items|tickets) in (cart|bag)',
            'zero (products|items|tickets) in .\w* (cart|bag)',
            'no (products|items|tickets) in (cart|bag)',
            'no (products|items|tickets) in .\w* (cart|bag)'
           ]

    return check_text(text, contains, [])


def check_alert_text(driver, contains, not_contains=None):
    '''
        Check alert text and close alert in checkout page.
    '''
    try:
        alert = driver.switch_to.alert

        if check_text(alert.text, contains, not_contains):
            alert.accept()
            return True
    except:
            return False

def check_if_domain_for_sale(text, domain):
    if re.search('domain .*{}.* for sale'.format(domain), text):
        return True
    
    return False