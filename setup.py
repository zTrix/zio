#!/usr/bin/env python2

from distutils.core import setup
from setuptools import find_packages

setup(
    name='zio',
    version='0.1',

    author='Wenlei Zhu',
    author_email='i@ztrix.me',
    url='https://github.com/zTrix/zio',

    license='LICENSE.txt',
    description='Unified io lib for pwning development written in python.',
    long_description=open('readme.md').read(),

    packages=find_packages(exclude=['test']),
    include_package_data=True,

    # Refers to test/test.py
    test_suite='test.test',
)
