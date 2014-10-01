#!/usr/bin/env python2

from distutils.core import setup
from setuptools import find_packages

from zio import __version__

setup(
    name='zio',
    version=__version__,

    author='Wenlei Zhu',
    author_email='i@ztrix.me',
    url='https://github.com/zTrix/zio',

    license='LICENSE.txt',
    keywords="zio pwning io expect-like",
    description='Unified io lib for pwning development written in python.',
    long_description=open('README.txt').read(),

    py_modules = ['zio'],

    # Refers to test/test.py
    test_suite='test.test',

    entry_points = {
        'console_scripts': [
            'zio=zio:main'
        ]
    },
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Operating System :: POSIX',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development',
        'Topic :: System',
        'Topic :: Terminals',
        'Topic :: Utilities',
    ],
)
