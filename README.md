### Tracing

Code that buys something from shops and saves traces.
Navigation and checkout page filling is heuristic based.

#### Mock Data Service

First we need to start data service with mock user data

1. Clone retrace_automation repo
```shell
git clone https://github.com/g2webservices/retrace_automation
```
2. Install dependencies.
Be carefull service uses python2

```shell
pip2 install falcon ujson faker barnum gunicorn
```

3. Run Service in a background in port 8989
```shell
(cd retrace_automation/backend; gunicorn -b 127.0.0.1:8989 r_service:api) &> mock_service.log &
```

#### Run script that traces random urls

Then we can run shops tracing.

1. Clone trace_automation repo
```shell
git clone https://github.com/g2webservices/trace_automation
```

We can start code that runs tracing on random sample shops code shop_crawler_stat_test.py

2. Use xvfb to run in headless mode:
```shell
sudo apt-get install xvfb
cd trace_automation/tracing
xvfb-run -s "-screen 0 1280x960x16" python shop_tracer_stat_test.py
```

3. Or it's possible to run jupyter-notebook 
```shell
jupyter-notebook trace_automation/tracing/shop_tracer.ipynb
```

### CV + Selenium
How to work with selenium having coordinates
```python
from selenium_helper import *

driver = create_chrome_driver()
driver.get('https://google.com')

btn = driver.find_element_by_css_selector('input[name="btnK"]')
text_field = driver.find_element_by_css_selector('input#lst-ib')

def get_element_center(elem):
    l = elem.location
    s = elem.size
    return (l['x'] + s['width'] // 2, l['y'] + s['height'] // 2)
    
x, y = get_element_center(text_field)
enter_text(driver, x, y, 'selenium')

x, y = get_element_center(btn)
click(driver, x, y)
```
