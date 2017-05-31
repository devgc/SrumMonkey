#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    name='SrumMonkey',
    version='1.0.0',
    description='A tool you can use to convert the Microsoft SRU edb database to a SQLite database',
    author='devgc',
    url='https://github.com/devgc',
    scripts = [
        'SrumMonkey.py',
        'CustomSqlFunctions.py'
    ],
    dependency_links = [
        'https://github.com/williballenthin/python-registry/tarball/master#egg=Registry-1.2.0',
        'https://github.com/devgc/GcHelpers/tarball/master#egg=gchelpers-0.0.1'
    ],
    install_requires = [
        'gchelpers==0.0.1',
        'python_registry',
        'XlsxWriter'
    ]
)
