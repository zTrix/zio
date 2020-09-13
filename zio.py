#!/usr/bin/env python
#===============================================================================
# The Star And Thank Author License (SATA)
# 
# Copyright (c) 2020 zTrix(i@ztrix.me)
# 
# Project Url: https://github.com/zTrix/zio
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software. 
# 
# And wait, the most important, you shall star/+1/like the project(s) in project url 
# section above first, and then thank the author(s) in Copyright section. 
# 
# Here are some suggested ways:
# 
#  - Email the authors a thank-you letter, and make friends with him/her/them.
#  - Report bugs or issues.
#  - Tell friends what a wonderful project this is.
#  - And, sure, you can just express thanks in your mind without telling the world.
# 
# Contributors of this project by forking have the option to add his/her name and 
# forked project url at copyright and project url sections, but shall not delete 
# or modify anything else in these two sections.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#===============================================================================

from __future__ import print_function
__version__ = "2.0.0"
__project__ = "https://github.com/zTrix/zio"

import os
import sys
import struct
import functools
try:
    from io import StringIO
except ImportError:
    from StringIO import StringIO

try:
    from termcolor import colored
except:
    # if termcolor import failed, use the following v1.1.0 source code of termcolor here
    # since termcolor use MIT license, SATA license above should be OK
    ATTRIBUTES = dict( list(zip([ 'bold', 'dark', '', 'underline', 'blink', '', 'reverse', 'concealed' ], list(range(1, 9)))))
    del ATTRIBUTES['']
    HIGHLIGHTS = dict( list(zip([ 'on_grey', 'on_red', 'on_green', 'on_yellow', 'on_blue', 'on_magenta', 'on_cyan', 'on_white' ], list(range(40, 48)))))
    COLORS = dict(list(zip(['grey', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white', ], list(range(30, 38)))))
    RESET = '\033[0m'

    def colored(text, color=None, on_color=None, attrs=None):
        fmt_str = '\033[%dm%s'
        if color is not None: text = fmt_str % (COLORS[color], text)
        if on_color is not None: text = fmt_str % (HIGHLIGHTS[on_color], text)
        if attrs is not None:
            for attr in attrs:
                text = fmt_str % (ATTRIBUTES[attr], text)

        text += RESET
        return text

# -------------------------------------------------
# =====> packing/unpacking related functions <=====

def convert_packing(endian, bits, arg, autopad=False):
    """
    endian: < for little endian, > for big endian
    bits: bit size of packing, valid values are 8, 16, 32, 64
    arg: integer or bytes
    """
    pfs = {8: 'B', 16: 'H', 32: 'I', 64: 'Q'}
    fmt = endian + pfs[bits]

    if isinstance(arg, int):
        return struct.pack(fmt, arg % (1 << bits))
    else:
        if len(arg) * 8 != bits:
            if autopad:
                arg = arg.ljust(bits//8, b'\x00') if endian == '<' else arg.rjust(bits//8, b'\x00')
        return struct.unpack(fmt, arg)[0]

l8 = functools.partial(convert_packing, '<', 8)
b8 = functools.partial(convert_packing, '>', 8)
l16 = functools.partial(convert_packing, '<', 16)
b16 = functools.partial(convert_packing, '>', 16)
l32 = functools.partial(convert_packing, '<', 32)
b32 = functools.partial(convert_packing, '>', 32)
l64 = functools.partial(convert_packing, '<', 64)
b64 = functools.partial(convert_packing, '>', 64)

# vi:set et ts=4 sw=4 ft=python :
