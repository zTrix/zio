#!/usr/bin/env python3
import os
import sys
import re
import random
import threading
import socket
import unittest
import time
import string
from io import BytesIO
from zio import *

from common import EchoServer, exec_cmdline, exec_script

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

        self.assertEqual(HEXDUMP(b'_' * 16 + b'abcde'), b'00000000: 5f5f 5f5f 5f5f 5f5f 5f5f 5f5f 5f5f 5f5f  ________________\n00000010: 6162 6364 65                             abcde\n')

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

        unprintable = [c for c in range(256) if chr(c) not in string.printable]
        random.shuffle(unprintable)
        unprintable = bytes(unprintable)

        io = zio(' '.join([sys.executable, '-u', os.path.join(os.path.dirname(sys.argv[0]), 'myprintf.py'), "'\\r\\n" + str(unprintable)[2:-1] + "\\n'"]), stdout=TTY_RAW, print_read=COLORED(REPR))
        rd = io.read()
        self.assertEqual(rd, b"\r\n" + unprintable + b"\n")

    # ------------------- Tests for both SocketIO and ProcessIO ---------------------

    def test_cat(self):
        for io in exec_cmdline('cat'):
            s = b'The Cat is #1\n'
            io.write(s)
            rs = io.readline()
            self.assertEqual(rs.strip(), s.strip(), 'TestCase Failure: got ' + repr(rs))

    def test_cat_eof(self):
        for io in exec_cmdline('cat'):
            s = b'The Cat is #1'
            io.write(s)
            io.send_eof()
            rs = io.read()
            self.assertEqual(rs.strip(), s.strip(), repr(rs))

    def test_cat_readline(self):
        for io in exec_cmdline('cat'):
            s = b'The Cat is #1'
            io.write(s + b'\n' + b'blah blah')
            rs = io.readline(keep=False)
            self.assertEqual(rs, s)

    def test_read_until(self):
        for io in exec_cmdline('cat'):
            s = ''.join([random.choice(string.printable[:62]) for x in range(1000)])
            s = s.encode()
            io.writeline(s)
            io.read(100)
            content = io.read_until(s[500:600])
            self.assertEqual(type(content), bytes)
            mid = io.read(100)
            self.assertEqual(mid, s[600:700])

            some = io.read_some()
            min_len = min(len(some) - 2, 300)
            self.assertEqual(some[:min_len], s[700:700+min_len])

    def test_read_timeout(self):
        for io in exec_cmdline('cat', timeout=1):

            with self.assertRaises(TimeoutError):
                io.read_until(b'____')

            with self.assertRaises(TimeoutError):
                io.read()

            with self.assertRaises(TimeoutError):
                io.read_some()

            with self.assertRaises(TimeoutError):
                io.read_line()

    def test_get_pass(self):
        # here we have to use TTY, or password won't get write thru
        # if you use subprocess, you will encounter same effect 
        for io in exec_script('userpass.py', stdin=TTY, read_echoback=True):
            io.read_until(b'Welcome')
            io.read_line()
            io.read_until(b'Username: ')
            io.write_line(b'user')
            io.read_until(b'Password: ')   # read_echoback must be set to True to make this work
            io.write_line(b'pass')
            io.read_line()
            line = io.read_line()
            self.assertEqual(line.strip(), b'Logged in', repr(line))
            io.read()
            io.close()
            self.assertEqual(io.exit_status(), 0)

    def test_xxd(self):
        for io in exec_cmdline('xxd', print_write=COLORED(REPR), print_read=COLORED(RAW, 'yellow'), socat_exec=''):
            rainbow = bytes([x for x in range(0, 256)])
            io.write_line(rainbow)
            io.send_eof()
            out = io.read()
            expected1 = b'0000000: 0001 0203 0405 0607 0809 0a0b 0c0d 0e0f  ................\n0000010: 1011 1213 1415 1617 1819 1a1b 1c1d 1e1f  ................\n0000020: 2021 2223 2425 2627 2829 2a2b 2c2d 2e2f   !"#$%&\'()*+,-./\n0000030: 3031 3233 3435 3637 3839 3a3b 3c3d 3e3f  0123456789:;<=>?\n0000040: 4041 4243 4445 4647 4849 4a4b 4c4d 4e4f  @ABCDEFGHIJKLMNO\n0000050: 5051 5253 5455 5657 5859 5a5b 5c5d 5e5f  PQRSTUVWXYZ[\\]^_\n0000060: 6061 6263 6465 6667 6869 6a6b 6c6d 6e6f  `abcdefghijklmno\n0000070: 7071 7273 7475 7677 7879 7a7b 7c7d 7e7f  pqrstuvwxyz{|}~.\n0000080: 8081 8283 8485 8687 8889 8a8b 8c8d 8e8f  ................\n0000090: 9091 9293 9495 9697 9899 9a9b 9c9d 9e9f  ................\n00000a0: a0a1 a2a3 a4a5 a6a7 a8a9 aaab acad aeaf  ................\n00000b0: b0b1 b2b3 b4b5 b6b7 b8b9 babb bcbd bebf  ................\n00000c0: c0c1 c2c3 c4c5 c6c7 c8c9 cacb cccd cecf  ................\n00000d0: d0d1 d2d3 d4d5 d6d7 d8d9 dadb dcdd dedf  ................\n00000e0: e0e1 e2e3 e4e5 e6e7 e8e9 eaeb eced eeef  ................\n00000f0: f0f1 f2f3 f4f5 f6f7 f8f9 fafb fcfd feff  ................\n0000100: 0a                                       .\n'
            expected2 = b'00000000: 0001 0203 0405 0607 0809 0a0b 0c0d 0e0f  ................\n00000010: 1011 1213 1415 1617 1819 1a1b 1c1d 1e1f  ................\n00000020: 2021 2223 2425 2627 2829 2a2b 2c2d 2e2f   !"#$%&\'()*+,-./\n00000030: 3031 3233 3435 3637 3839 3a3b 3c3d 3e3f  0123456789:;<=>?\n00000040: 4041 4243 4445 4647 4849 4a4b 4c4d 4e4f  @ABCDEFGHIJKLMNO\n00000050: 5051 5253 5455 5657 5859 5a5b 5c5d 5e5f  PQRSTUVWXYZ[\\]^_\n00000060: 6061 6263 6465 6667 6869 6a6b 6c6d 6e6f  `abcdefghijklmno\n00000070: 7071 7273 7475 7677 7879 7a7b 7c7d 7e7f  pqrstuvwxyz{|}~.\n00000080: 8081 8283 8485 8687 8889 8a8b 8c8d 8e8f  ................\n00000090: 9091 9293 9495 9697 9899 9a9b 9c9d 9e9f  ................\n000000a0: a0a1 a2a3 a4a5 a6a7 a8a9 aaab acad aeaf  ................\n000000b0: b0b1 b2b3 b4b5 b6b7 b8b9 babb bcbd bebf  ................\n000000c0: c0c1 c2c3 c4c5 c6c7 c8c9 cacb cccd cecf  ................\n000000d0: d0d1 d2d3 d4d5 d6d7 d8d9 dadb dcdd dedf  ................\n000000e0: e0e1 e2e3 e4e5 e6e7 e8e9 eaeb eced eeef  ................\n000000f0: f0f1 f2f3 f4f5 f6f7 f8f9 fafb fcfd feff  ................\n00000100: 0a                                       .\n'
            self.assertIn(out.replace(b'\r\n', b'\n'), (expected1, expected2), repr(out))

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
