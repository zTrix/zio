#!/usr/bin/env python3
import os
import sys
import re
import random
import threading
import socket
import unittest
import time
from io import BytesIO
from zio import *

from common import EchoServer

class ZIOTestCase(unittest.TestCase):

    def test_packing_unpacking(self):
        self.assertEqual(l32(0), b'\x00\x00\x00\x00')
        self.assertEqual(b32(1), b'\x00\x00\x00\x01')
        self.assertEqual(l16(0x35), b'\x35\x00')
        self.assertEqual(l32(b'\x83\x06\x40\x00'), 0x400683)
        self.assertEqual(l64(b'\x83\x06\x40', autopad=True), 0x400683)
        self.assertEqual(b16(b'\x23', autopad=True), 0x23)
        self.assertEqual(b32(b'\x12\x34', autopad=True), 0x1234)
        self.assertEqual(l32([0, 1, 2]), b'\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00')
        self.assertEqual(l32(b'\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00'), [0, 1, 2])
        self.assertEqual(l32(b'\x00\x00\x00\x00\x01\x00\x00\x00\x02', autopad=True), [0, 1, 2])
        self.assertEqual(b32(b'\x00\x00\x00\x00\x01\x00\x00\x00\x02', autopad=True), [0, 0x1000000, 2])

        with self.assertRaises(ValueError):
            b32(b'\x00\x00\x00\x00\x01\x00\x00\x00\x02')

    def test_encoding(self):
        a = b"\xd8;:Dx-;Fx)=Yx%'L(*6\x01797Sx;:Dx#3[!o6N?\xb0"
        b = b'XOR!'

        self.assertEqual(xor(a, b), b'\x80the big fox jumped over the lazy dog\xff')

        self.assertEqual(tohex(b'\xde\xad\xbe\xaf'), b'deadbeaf')
        self.assertEqual(unhex('deadbeaf'), b'\xde\xad\xbe\xaf')

        self.assertEqual(unhex('11223', autopad='right'), b'\x11\x22\x30')
        self.assertEqual(unhex('11223', autopad='left'), b'\x01\x12\x23')
        with self.assertRaises(ValueError):
            unhex('11223', autopad=False)

        self.assertIn(REPR(b'asdf'), b"b'asdf'\r\n", b'b"asdf"\r\n')

        self.assertEqual(EVAL(b'xx\\x33'), b'xx\x33')
        self.assertEqual(EVAL(b'\\\\x\\tx\\xf1\\r\\n'), b'\\x\tx\xf1\r\n')

    # ------------------- SocketIO Tests ---------------------

    def test_socket_io(self):
        server = EchoServer(content=[b'hello world\n', b'\xe4\xbd\xa0\xe5\xa5\xbd\xe4\xb8\x96\xe7\x95\x8c\n'], sleep_after=0.5)
        server.start()
        time.sleep(0.1)
        logfile = BytesIO()

        io = zio(server.target_addr(), logfile=logfile, print_read=True, print_write=False)

        self.assertEqual(io.mode(), 'socket')

        content = io.read(5)
        self.assertEqual(content, b'hello')
        self.assertEqual(logfile.getvalue(), b'hello')

        content = io.read(1)
        self.assertEqual(content, b' ')

        content = io.read(5)
        self.assertEqual(content, b'world')

        self.assertEqual(logfile.getvalue(), b'hello world')

        content = io.read()
        self.assertEqual(content, b'\n\xe4\xbd\xa0\xe5\xa5\xbd\xe4\xb8\x96\xe7\x95\x8c\n')

        io.close()
        self.assertEqual(logfile.getvalue(), 'hello world\n你好世界\n'.encode())

    def test_socket_io_read_until(self):
        server = EchoServer(content=[b'Welcome to Math World\n', b'input:', b'received\n'], sleep_between=0.5)
        server.start()
        time.sleep(0.1)
        logfile = BytesIO()

        io = zio(server.target_addr(), logfile=logfile, print_read=True, print_write=False)
        content = io.read_until(b'input:')
        self.assertEqual(content, b'Welcome to Math World\ninput:')
        self.assertEqual(logfile.getvalue(), b'Welcome to Math World\ninput:')

        line = io.read_line(keep=False)
        self.assertEqual(line, b'received')
        self.assertEqual(logfile.getvalue(), b'Welcome to Math World\ninput:received\n')

        with self.assertRaises(EOFError):
            io.read_until(b'____')

        io.read()
        io.close()

    def test_socket_io_read_until_timeout(self):
        server = EchoServer(content=[b'Welcome to Math World\n', b'input:', b'received\n'], sleep_before=2, sleep_between=1)
        server.start()
        time.sleep(0.1)
        logfile = BytesIO()

        io = zio(server.target_addr(), logfile=logfile, print_read=True, print_write=False)
        content = io.read_until_timeout(1.4)
        self.assertEqual(content, b'')

        content = io.read_until_timeout(1)
        self.assertEqual(content, b'Welcome to Math World\n')

        content = io.read_until_timeout(1.5)
        self.assertEqual(content, b'input:')

        time.sleep(2)
        self.assertEqual(io.readable(), True)
        content = io.read_until_timeout(1)
        self.assertEqual(content, b'received\n')

        io.close()

    def test_match_pattern(self):
        self.assertEqual(match_pattern(b'study', b'good good study, day day up'), (10, 15))
        self.assertEqual(match_pattern(re.compile(b'study'), b'good good study, day day up'), (10, 15))
        self.assertEqual(match_pattern(lambda x: (x.find(b'study'), x.find(b'study')+5), b'good good study, day day up'), (10, 15))

        self.assertEqual(match_pattern(b'wont be found', b'asfasdasd'), (-1, -1))
        self.assertEqual(match_pattern(re.compile(b'study'), b'good good good good'), (-1, -1))

    def test_socket_write(self):
        server = EchoServer(content=[b'Welcome to Math World\n', b'input:', b'received\n'], sleep_between=0.5)
        server.start()
        time.sleep(0.1)
        logfile = BytesIO()

        io = zio(server.target_addr(), logfile=logfile, print_read=False, print_write=True)
        self.assertEqual(io.write(b'asdf'), 4)
        self.assertEqual(logfile.getvalue(), b'asdf')

        io.close()
        self.assertEqual(io.is_closed(), True)

    def test_attach_socket(self):
        server = EchoServer(content=[b'Welcome to Math World\n', b'input:', b'received\n'], sleep_between=0.5)
        server.start()
        time.sleep(0.1)
        logfile = BytesIO()

        s = socket.create_connection(server.target_addr())
        s.recv(22)

        io = zio(s, logfile=logfile, print_read=True, print_write=False)
        content = io.read_until(b'input:')
        self.assertEqual(content, b'input:')

        content = io.read_line()
        self.assertEqual(content, b'received\n')

        self.assertEqual(logfile.getvalue(), b'input:received\n')
        io.close()

    # ------------------- ProcessIO Tests ---------------------

    def test_send_eof(self):
        logfile = BytesIO()

        io = zio('cat', logfile=logfile, print_read=True, print_write=False)
        io.writeline(b'____')

        io.send_eof()
        content = io.read()
        self.assertEqual(content, b'____\n')
        self.assertEqual(logfile.getvalue(), b'____\n')

        io.close()

    def test_hex_read(self):
        logfile = BytesIO()

        io = zio('cat', logfile=logfile, print_read=HEX, print_write=False)

        io.writeline(b'____')
        content = io.readline(keep=False)

        self.assertEqual(content, b'____')
        self.assertEqual(logfile.getvalue(), b'5f5f5f5f0a\r\n')

        io.close()

    def test_tty(self):
        io = zio('tty')
        out = io.read()
        self.assertEqual(out.strip(), b'not a tty', repr(out))
        io.close()

        io = zio('tty', stdin=TTY)
        out = io.read()
        self.assertTrue(out.strip().startswith(b'/dev/'), repr(out))
        io.close()

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
