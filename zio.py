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
import socket
import signal
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

# TODO: hex/unhex/xor some encoding functions

def is_hostport_tuple(target):
    return type(target) == tuple and len(target) == 2 and isinstance(target[1], int) and target[1] >= 0 and target[1] < 65536


# -------------------------------------------------
# =====> zio class <=====

PIPE = 'pipe'           # io mode (process io): send all characters untouched, but use PIPE, so libc cache may apply
TTY = 'tty'             # io mode (process io): normal tty behavier, support Ctrl-C to terminate, and auto \r\n to display more readable lines for human
TTY_RAW = 'ttyraw'      # io mode (process io): send all characters just untouched

def COLORED(f, color='cyan', on_color=None, attrs=None):
    return lambda s : colored(f(s), color, on_color, attrs)

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
                        self.buffer.clear()
                        return ret
                    else:
                        raise Exception('EOF occured before full size read, buffer = %s' % self.buffer)
                self.buffer.extend(incoming)

            if not is_read_all and len(self.buffer) >= size:
                ret = bytes(self.buffer[:size])
                self.buffer = self.buffer[size:]
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
        '''
        return self.sock.recv(size)

    def send(self, buf):
        return self.sock.sendall(buf)

    def close(self):
        self.sock.close()

    def __repr__(self):
        return repr(self.sock)

# export useful things

__all__ = [
    'l8', 'b8', 'l16', 'b16', 'l32', 'b32', 'l64', 'b64', 
    'colored',
    'zio',
]

# vi:set et ts=4 sw=4 ft=python :
