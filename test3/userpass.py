#!/usr/bin/env python

from __future__ import print_function

import sys
import getpass

# python2 python3 shim
if sys.version_info[0] < 3:
    input = raw_input           # pylint: disable=undefined-variable

print('Welcome')

user = input('Username: ')

# note the stream param, if leave blank, zio won't read password prompt, because it's echoed back
# from tty stdin, while zio handle stdin and stdout/stderr in two ttys.
pswd = getpass.getpass('Password: ', stream=sys.stdout)

if user == 'user' and pswd == 'pass':
    print('Logged in')
else:
    print('Invalid', repr(user), repr(pswd))

