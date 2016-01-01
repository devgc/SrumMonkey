#!/usr/bin/env python

from distutils.core import setup

setup(name='SrumMonkey',
      version='1.0',
      description='a tool you can use to convert the Microsoft SRU edb database to a SQLite database',
      author='devgc',
      url='https://github.com/devgc',
      scripts=['SrumMonkey.py', 'CustomSqlFunctions.py']
     )
