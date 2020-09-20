#!/usr/bin/env python2
# encoding: utf-8
import os
import sys
import re
import random
import time
import threading
import socket
import unittest
import string
from StringIO import StringIO as BytesIO
import unittest
from zio import *

from common import EchoServer

class ZIOTestCase(unittest.TestCase):

    def test_packing_unpacking(self):
        self.assertEqual(l32(0), '\x00\x00\x00\x00')
        self.assertEqual(b32(1), '\x00\x00\x00\x01')
        self.assertEqual(l16(0x35), '\x35\x00')
        self.assertEqual(l32('\x83\x06\x40\x00'), 0x400683)
        self.assertEqual(l64('\x83\x06\x40', autopad=True), 0x400683)
        self.assertEqual(b16('\x23', autopad=True), 0x23)
        self.assertEqual(b32('\x12\x34', autopad=True), 0x1234)
        self.assertEqual(l32([0, 1, 2]), '\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00')
        self.assertEqual(l32('\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00'), [0, 1, 2])
        self.assertEqual(l32('\x00\x00\x00\x00\x01\x00\x00\x00\x02', autopad=True), [0, 1, 2])
        self.assertEqual(b32('\x00\x00\x00\x00\x01\x00\x00\x00\x02', autopad=True), [0, 0x1000000, 2])

        # python 2.6 2.7 compatible way
        self.assertRaises(ValueError, b32, '\x00\x00\x00\x00\x01\x00\x00\x00\x02')

    def test_encoding(self):
        a = b"\xd8;:Dx-;Fx)=Yx%'L(*6\x01797Sx;:Dx#3[!o6N?\xb0"
        b = b'XOR!'

        self.assertEqual(xor(a, b), b'\x80the big fox jumped over the lazy dog\xff')

        self.assertEqual(tohex(b'\xde\xad\xbe\xaf'), b'deadbeaf')
        self.assertEqual(unhex('deadbeaf'), b'\xde\xad\xbe\xaf')

        self.assertEqual(unhex('11223', autopad='right'), b'\x11\x22\x30')
        self.assertEqual(unhex('11223', autopad='left'), b'\x01\x12\x23')

        self.assertRaises(ValueError, unhex, '11223', autopad=False)

        self.assertIn(REPR(b'asdf'), "b'asdf'\r\n", 'b"asdf"\r\n')

        self.assertEqual(EVAL(b'xx\\x33'), b'xx\x33')
        self.assertEqual(EVAL(b'\\\\x\\tx\\xf1\\r\\n'), b'\\x\tx\xf1\r\n')

    # ------------------- SocketIO Tests ---------------------

    def test_socket_io(self):
        server = EchoServer(content=[b'hello world\n', b'\xe4\xbd\xa0\xe5\xa5\xbd\xe4\xb8\x96\xe7\x95\x8c\n'])
        server.start()
        time.sleep(0.1)
        logfile = BytesIO()

        io = zio(server.target_addr(), logfile=logfile, print_read=True, print_write=False)

        self.assertEqual(io.mode(), 'socket')

        content = io.read(5)
        self.assertEqual(content, b'hello')
        self.assertEqual(logfile.getvalue(), u'hello')

        content = io.read(1)
        self.assertEqual(content, b' ')

        content = io.read(5)
        self.assertEqual(content, b'world')

        content = io.read()
        self.assertEqual(content, b'\n\xe4\xbd\xa0\xe5\xa5\xbd\xe4\xb8\x96\xe7\x95\x8c\n')

        io.close()
        self.assertEqual(logfile.getvalue(), u'hello world\n你好世界\n'.encode('utf-8'))

    def test_socket_io_read_until(self):
        server = EchoServer(content=[b'Welcome to Math World\n', b'input:', b'received\n'], sleep_between=0.5)
        server.start()
        time.sleep(0.1)
        logfile = BytesIO()

        io = zio(server.target_addr(), logfile=logfile, print_read=True, print_write=False)
        content = io.read_until(b'input:')
        self.assertEqual(content, b'Welcome to Math World\ninput:')
        self.assertEqual(logfile.getvalue(), 'Welcome to Math World\ninput:')

        line = io.read_line(keep=False)
        self.assertEqual(line, b'received')
        self.assertEqual(logfile.getvalue(), 'Welcome to Math World\ninput:received\n')

        self.assertRaises(EOFError, io.read_until, b'____')

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
        self.assertEqual(logfile.getvalue(), u'asdf')

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
        self.assertTrue(out.strip().startswith('/dev/'), repr(out))
        io.close()

    def test_uname(self):
        io = zio('uname', stdout=PIPE)
        r = io.read()
        io.close()
        self.assertEqual(r.strip(), os.uname()[0].encode())

        self.assertEqual(io.exit_status(), 0)

    def test_tty_raw_out(self):
        s = []
        ans = []
        for i in range(10):
            r = random.randint(0,1)
            s.append('%d%s' % (i, r and '\\r\\n' or '\\n'))
            ans.append('%d%s' % (i, r and '\r\n' or '\n'))
        ans = ''.join(ans)
        cmd = "printf '" + ''.join(s) + "'"
        io = zio(cmd, stdout=TTY_RAW)
        rd = io.read()
        io.close()
        self.assertEqual(rd, ans.encode())

        unprintable = [chr(c) for c in range(256) if chr(c) not in string.printable]
        random.shuffle(unprintable)
        unprintable = ''.join(unprintable)

        io = zio(' '.join([sys.executable, '-u', os.path.join(os.path.dirname(sys.argv[0]), 'myprintf.py'), "'\\r\\n" + repr(unprintable)[1:-1] + "\\n'"]), stdout=TTY_RAW, print_read=COLORED(REPR))
        rd = io.read()
        self.assertEqual(rd, b"\r\n" + unprintable + b"\n")

if sys.version_info[1] < 7:
    # python2.6 shim

    def assertIn(self, member, container, msg=None):
        """Just like self.assertTrue(a in b), but with a nicer default message."""
        if member not in container:
            standardMsg = '%s not found in %s' % (repr(member), repr(container))
            raise self.failureException, (msg or standardMsg)   # pylint: disable=syntax-error
    ZIOTestCase.assertIn = assertIn

    def assertNotIn(self, member, container, msg=None):
        """Just like self.assertTrue(a not in b), but with a nicer default message."""
        if member in container:
            standardMsg = '%s unexpectedly found in %s' % (repr(member), repr(container))
            raise self.failureException, (msg or standardMsg)   # pylint: disable=syntax-error
    ZIOTestCase.assertNotIn = assertNotIn

if __name__ == '__main__':
    if sys.version_info[1] < 7:
        unittest.main()
    else:
        unittest.main(verbosity=2, failfast=True)
