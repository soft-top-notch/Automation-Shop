### Crawling

#### Fake Data Service

First we need to start Fake data service.

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

1. Clone trace_automation repo
```shell
git clone https://github.com/g2webservices/trace_automation
```

To measure quality run code shop_crawler_stat_test.py

2. Use xvfb to run in headless mode:
```shell
sudo apt-get install xvfb
xvfb-run python trace_automation/crawler/shop_crawler_stat_test.py
```
