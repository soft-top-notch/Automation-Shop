FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive

# Install xvfb and common tools
RUN apt-get update && apt-get install -y \
    software-properties-common \
    unzip \
    curl

RUN apt-get install -y xvfb libxi6 libgconf-2-4 x11vnc x11-xkb-utils xfonts-100dpi xfonts-75dpi xfonts-scalable xfonts-cyrillic x11-apps

# Install Chrome for Selenium
RUN curl https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -o /chrome.deb
RUN dpkg -i /chrome.deb || apt-get install -yf
RUN rm /chrome.deb

# Install chromedriver for Selenium
RUN curl https://chromedriver.storage.googleapis.com/2.41/chromedriver_linux64.zip -o /chromedriver_linux64.zip
RUN unzip chromedriver_linux64.zip
RUN mv chromedriver /usr/bin/chromedriver
RUN chmod +x /usr/bin/chromedriver

# Python, setuptools
RUN apt-get install -y python3-dev python3-setuptools python3-pip

# Packages required by Pillow
RUN apt-get install -y libpng-dev libtiff5-dev libjpeg8-dev zlib1g-dev \
    libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python-tk

RUN pip3 install Pillow	

ADD . /code
WORKDIR /code
RUN python3 /code/setup.py install

CMD echo $RABBIT_HOST; echo $MONGO_HOST;xvfb-run -a python3 tracing/shop_tracer_worker.py


