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
from __future__ import division

__version__ = "2.0.0"
__project__ = "https://github.com/zTrix/zio"

import os
import sys
import struct
import functools
import socket
import signal
import ast
import binascii

# python2 python3 shim
if sys.version_info.major < 3:
    input = raw_input           # pylint: disable=undefined-variable
else:
    unicode = str
    unichr = chr

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

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
given endian, bits spec, do the following
    convert between bytes <--> int
    convert between bytes <--> [int]

params:
    endian: < for little endian, > for big endian
    bits: bit size of packing, valid values are 8, 16, 32, 64
    arg: integer or bytes
    autopad: auto pad input string to required length if needed
    """
    pfs = {8: 'B', 16: 'H', 32: 'I', 64: 'Q'}

    if isinstance(arg, bytes):      # bytes -> int or [int]
        c = bits // 8
        r = len(arg) % c
        if r != 0:
            if autopad:
                arg = arg[:len(arg) // c * c] + (arg[-r:].ljust(c, b'\x00') if endian == '<' else arg[-r:].rjust(c, b'\x00'))
            else:
                raise ValueError('bad input length, expected multiple of %d, got %d. Fix length manually or use autopad=True' % (c, len(arg)))
        unpacked = struct.unpack(endian + pfs[bits] * (len(arg) // c), arg)
        return list(unpacked) if len(unpacked) > 1 else unpacked[0]
    else:                           # int or [int] -> bytes
        args = list(arg) if isinstance(arg, (list, tuple)) else [arg]
        return struct.pack(endian + pfs[bits] * len(args), *args)

l8 = functools.partial(convert_packing, '<', 8)
b8 = functools.partial(convert_packing, '>', 8)
l16 = functools.partial(convert_packing, '<', 16)
b16 = functools.partial(convert_packing, '>', 16)
l32 = functools.partial(convert_packing, '<', 32)
b32 = functools.partial(convert_packing, '>', 32)
l64 = functools.partial(convert_packing, '<', 64)
b64 = functools.partial(convert_packing, '>', 64)

# -------------------------------------------------
# =====> utility functions <=====

def bytes2hex(s):
    '''
    Union{bytes, unicode} -> bytes
    '''
    if isinstance(s, unicode):
        s = s.encode()
    return binascii.hexlify(s)

def hex2bytes(s, autopad=False):
    '''
    bytes -> bytes
    '''
    if isinstance(s, unicode):
        s = s.encode()
    s = s.strip()
    if len(s) % 2 == 1:
        if autopad == 'left' or autopad == True:
            s = b'0' + s
        elif autopad == 'right':
            s = s + b'0'
        else:
            raise ValueError('invalid length of hex bytes: %d, should be multiple of 2. Use autopad=True to fix automatically' % len(s))
    return binascii.unhexlify(s)

tohex = bytes2hex
unhex = hex2bytes

if sys.version_info.major < 3:
    def xor(a, b):
        '''
        bytes -> bytes -> bytes
        the first param a must be longer than or equal to the length of the second param
        '''
        return b''.join([chr(ord(c) ^ ord(b[i % len(b)])) for i, c in enumerate(a)])
else:
    def xor(a, b):
        '''
        bytes -> bytes -> bytes
        the first param a must be longer than or equal to the length of the second param
        '''
        return bytes([c ^ b[i % len(b)] for i, c in enumerate(a)])

def is_hostport_tuple(target):
    return type(target) == tuple and len(target) == 2 and isinstance(target[1], int) and target[1] >= 0 and target[1] < 65536

# -------------------------------------------------
# =====> zio class <=====

PIPE = 'pipe'           # io mode (process io): send all characters untouched, but use PIPE, so libc cache may apply
TTY = 'tty'             # io mode (process io): normal tty behavier, support Ctrl-C to terminate, and auto \r\n to display more readable lines for human
TTY_RAW = 'ttyraw'      # io mode (process io): send all characters just untouched

def COLORED(f, color='cyan', on_color=None, attrs=None):
    return lambda s : colored(f(s), color, on_color, attrs)

# read/write transform functions
# bytes -> (printable) unicode
# note: here we use unicode literal to enforce unicode in spite of python2
if sys.version_info.major < 3:
    def REPR(s): return u'b' + repr(s) + u'\r\n'
else:
    def REPR(s): return str(s) + u'\r\n'

def EVAL(s): return ast.literal_eval(s.decode(u'latin-1'))

def HEX(s): return bytes2hex(s).decode() + u'\r\n'
TOHEX = HEX
def UNHEX(s): return hex2bytes(s).decode()

if sys.version_info.major < 3:
    def BIN(s): return u' '.join([format(ord(x),'08b') for x in str(s)]) + u'\r\n'
else:
    def BIN(s): return u' '.join([format(x,'08b') for x in s]) + u'\r\n'

def UNBIN(s, autopad=False):
    s = bytes(filter(lambda x: x in b'01', s))
    if len(s) % 8 != 0:
        extra = 8 - len(s) % 8
        if autopad == 'left' or autopad == True:
            s = (b'0' * extra) + s
        elif autopad == 'right':
            s = s + (b'0' * extra)
        else:
            raise ValueError('invalid length of 01 bytestring: %d, should be multiple of 8. Use autopad=True to fix automatically' % len(s))
    return u''.join([unichr(int(s[x:x+8],2)) for x in range(0, len(s), 8)])

# common encoding: utf-8, gbk, latin-1, ascii
def RAW(s, encoding='utf-8'): return s.decode(encoding)
def NONE(s): return u''


class zio(object):
    
    def __init__(self, target,
        stdin=PIPE,
        stdout=TTY_RAW,
        print_read=True,
        print_write=True,
        timeout=8,
        cwd=None,
        env=None,
        sighup=signal.SIG_DFL,
        write_delay=0.05,
        debug=None,
        logfile=sys.stderr,
    ):
        """
        zio is an easy-to-use io library for pwning development, supporting an unified interface for local process pwning and remote tcp socket io

        example:

        io = zio(('localhost', 80))
        io = zio(socket.create_connection(('127.0.0.1', 80)))
        io = zio('ls -l')
        io = zio(['ls', '-l'])

        params:
            print_read = bool, if true, print all the data read from target
            print_write = bool, if true, print all the data sent out
        """

        if not target:
            raise Exception('cmdline or socket not provided for zio, try zio("ls -l")')

        self.target = target
        self.print_read = print_read
        self.print_write = print_write
        self.logfile = logfile

        # zio object itself is a buffered reader/writer
        self.buffer = bytearray()

        self.debug = debug

        if isinstance(timeout, int) and timeout > 0:
            self.timeout = timeout
        else:
            self.timeout = 8

        if is_hostport_tuple(self.target) or isinstance(self.target, socket.socket):
            self.io = SocketIO(self.target)
        else:
            # do process io
            raise NotImplementedError

    def log_read(self, byte_buf):
        '''
        bytes -> IO unicode
        '''
        if self.print_read:
            content = self.read_transform(byte_buf)
            self.logfile.write(content)
            self.logfile.flush()

    def log_write(self, byte_buf):
        '''
        bytes -> IO unicode
        '''
        if self.print_write:
            content = self.write_transform(byte_buf)
            self.logfile.write(content)
            self.logfile.flush()

    @property
    def print_read(self):
        return self.read_transform is not None and self.read_transform is not NONE

    @print_read.setter
    def print_read(self, value):
        if value == True:
            self.read_transform = RAW
        elif value == False:
            self.read_transform = NONE
        elif callable(value):
            self.read_transform = value
        else:
            raise ValueError('bad print_read value')
        
        assert callable(self.read_transform)

    @property
    def print_write(self):
        return self.write_transform is not None and self.write_transform is not NONE

    @print_write.setter
    def print_write(self, value):
        if value == True:
            self.write_transform = RAW
        elif value == False:
            self.write_transform = NONE
        elif callable(value):
            self.write_transform = value
        else:
            raise ValueError('bad print_read value')
        
        assert callable(self.write_transform)

    def read(self, size=None):
        '''
        if size is -1 or None, then read all bytes available until EOF
        if size is a positive integer, read exactly `size` bytes and return
        raise Exception if EOF occurred before full size read
        '''
        is_read_all = size is None or size < 0
        while True:
            if is_read_all or len(self.buffer) < size:
                incoming = self.io.recv(1536)
                if incoming is None:
                    if is_read_all:
                        ret = bytes(self.buffer)
                        # self.buffer.clear()   # note: python2 does not support bytearray.clear()
                        self.buffer = bytearray()
                        self.log_read(ret)
                        return ret
                    else:
                        raise Exception('EOF occured before full size read, buffer = %s' % self.buffer)
                self.buffer.extend(incoming)

            if not is_read_all and len(self.buffer) >= size:
                ret = bytes(self.buffer[:size])
                self.buffer = self.buffer[size:]
                self.log_read(ret)
                return ret

    read_exact = read
    def read_to_end(self):
        return self.read(size=-1)

    def read_line(self):
        pass

    readline = read_line

    def read_until(self, keep=True):
        '''
        '''
        pass

    readuntil = read_until

    def read_some(self, size=None):
        '''
        just read 1 or more available bytes (less than size) and return
        '''
        pass

    def close(self):
        self.io.close()

class SocketIO:
    def __init__(self, target, timeout=None):
        self.timeout = timeout
        if isinstance(target, socket.socket):
            self.sock = target
        else:
            self.sock = socket.create_connection(target, self.timeout)

    @property
    def rfd(self):
        return self.sock.fileno()

    @property
    def wfd(self):
        return self.sock.fileno()

    def recv(self, size=None):
        '''
        recv 1 or more available bytes then return
        return None to indicate EOF
        '''
        b = self.sock.recv(size)
        if not b:
            return None
        return b

    def send(self, buf):
        return self.sock.sendall(buf)

    def close(self):
        self.sock.close()

    def __repr__(self):
        return repr(self.sock)

# export useful things

__all__ = [
    'l8', 'b8', 'l16', 'b16', 'l32', 'b32', 'l64', 'b64', 'convert_packing',
    'colored',
    'xor', 'bytes2hex', 'hex2bytes', 'tohex', 'unhex',
    'zio',
    'HEX', 'TOHEX', 'UNHEX', 'EVAL', 'REPR', 'RAW', 'NONE',
    'TTY', 'PIPE', 'TTY_RAW',
]

# vi:set et ts=4 sw=4 ft=python :
