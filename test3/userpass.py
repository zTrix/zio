#!/usr/bin/env python

from __future__ import print_function

import sys
import getpass

# python2 python3 shim
if sys.version_info[0] < 3:
    input = raw_input           # pylint: disable=undefined-variable

print('Welcome')

user = input('Username: ')

pswd = getpass.getpass('Password: ')

if user == 'user' and pswd == 'pass':
    print('Logged in')
else:
    print('Invalid', repr(user), repr(pswd))

