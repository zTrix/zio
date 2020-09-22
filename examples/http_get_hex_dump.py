#!/usr/bin/env python

import sys
from zio import *

io = zio(('github.com', 80), print_read=COLORED(HEXDUMP, 'yellow'), print_write=COLORED(HEXDUMP_INDENT8, 'cyan'))
io.write(b'GET / HTTP/1.0\r\n\r\n')
io.read()

io.close()
