# from setuptools import setup
from setuptools import setup, find_packages

setup(
     name='tracing',
     version='0.1',
     description='Tools for tracing',
     author='G2 Team',
     install_requires=['tensorflow'],
     packages=find_packages(),
     include_package_data=True,
     package_data={'tracing': ['tracing/js/*.js']}
)
