#!/usr/bin/env python2

import os, sys, unittest, string, time, random
from zio import *

class Test(unittest.TestCase):

    def setUp(self):
        pass

    def exec_script(self, script):
        py = which('python2') or which('python')
        self.assertNotEqual(py, None)
        return zio([py, os.path.join(os.path.dirname(sys.argv[0]), script)])
    
    def test_uname(self):
        print ''
        io = zio('uname')
        rs = io.read()
        self.assertEqual(rs.strip(), os.uname()[0], repr(rs))

    def test_cat(self):
        print ''
        io = zio('cat')
        s = 'The Cat is #1\n'
        io.write(s)
        rs = io.readline()
        self.assertEqual(rs.strip(), s.strip(), 'TestCase Failure: got ' + repr(rs))
        io.close()

    def test_cat_eof(self):
        print ''
        io = zio('cat')
        s = 'The Cat is #1'
        io.write(s)
        io.writeeof()
        rs = io.read()
        self.assertEqual(rs.strip(), s.strip(), repr(rs))
        io.close()

    def test_cat_readline(self):
        print ''
        io = zio('cat')
        s = 'The Cat is #1'
        io.write(s + '\n' + 'blah blah')
        rs = io.readline()
        self.assertEqual(rs.strip(), s)
        io.close()

    def test_read_until(self):
        print ''
        io = zio('cat')
        s = ''.join([random.choice(string.printable[:62]) for x in range(1000)])
        io.writeline(s)
        io.read(100)
        io.read_until(s[500:600])
        mid = io.read(100)
        self.assertEqual(mid, s[600:700])

    def test_get_pass(self):
        print 
        io = self.exec_script('userpass.py')
        io.read_until('Welcome')
        io.readline()
        io.read_until('Username: ')
        io.writeline('user')
        io.read_until('Password: ')   # note the 'stream = sys.stdout' line in userpass.py, which makes this prompt readable here, else Password will be echoed back from stdin(tty), not stdout, so you will never read this!!
        io.writeline('pass')
        io.writeeof()
        io.readline()
        line = io.readline()
        self.assertEqual(line.strip(), 'Logged in', repr(line))
        io.close()

    def test_http(self):
        io = zio(('ifconfig.me', 80))
        io.write('GET / HTTP/1.1\r\nHOST: ifconfig.me\r\nUser-Agent: curl\r\n\r\n')
        self.assertEqual(io.read(5), 'HTTP/', 'bad http start')
        self.assertEqual(io.readline().strip(), '1.1 200 OK', 'bad http status')
        io.close()

    def test_xxd(self):
        print ''
        io = zio('xxd', print_write = False)
        io.write(''.join([chr(x) for x in range(0, 256)]) + '\n')
        io.writeeof()
        self.assertEqual(io.read(), '0000000: 0001 0203 0405 0607 0809 0a0b 0c0d 0e0f  ................\r\n0000010: 1011 1213 1415 1617 1819 1a1b 1c1d 1e1f  ................\r\n0000020: 2021 2223 2425 2627 2829 2a2b 2c2d 2e2f   !"#$%&\'()*+,-./\r\n0000030: 3031 3233 3435 3637 3839 3a3b 3c3d 3e3f  0123456789:;<=>?\r\n0000040: 4041 4243 4445 4647 4849 4a4b 4c4d 4e4f  @ABCDEFGHIJKLMNO\r\n0000050: 5051 5253 5455 5657 5859 5a5b 5c5d 5e5f  PQRSTUVWXYZ[\\]^_\r\n0000060: 6061 6263 6465 6667 6869 6a6b 6c6d 6e6f  `abcdefghijklmno\r\n0000070: 7071 7273 7475 7677 7879 7a7b 7c7d 7e7f  pqrstuvwxyz{|}~.\r\n0000080: 8081 8283 8485 8687 8889 8a8b 8c8d 8e8f  ................\r\n0000090: 9091 9293 9495 9697 9899 9a9b 9c9d 9e9f  ................\r\n00000a0: a0a1 a2a3 a4a5 a6a7 a8a9 aaab acad aeaf  ................\r\n00000b0: b0b1 b2b3 b4b5 b6b7 b8b9 babb bcbd bebf  ................\r\n00000c0: c0c1 c2c3 c4c5 c6c7 c8c9 cacb cccd cecf  ................\r\n00000d0: d0d1 d2d3 d4d5 d6d7 d8d9 dadb dcdd dedf  ................\r\n00000e0: e0e1 e2e3 e4e5 e6e7 e8e9 eaeb eced eeef  ................\r\n00000f0: f0f1 f2f3 f4f5 f6f7 f8f9 fafb fcfd feff  ................\r\n0000100: 0a                                       .\r\n', 'invalid output of xxd')
        
if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(Test)

    tests = []

    if len(sys.argv) > 1:
        tests.extend(sys.argv[1:])

    if len(tests):
        suite = unittest.TestSuite(map(Test, tests))

    rs = unittest.TextTestRunner(verbosity = 2).run(suite)
    if len(rs.errors) > 0 or len(rs.failures) > 0:
        sys.exit(10)
    else:
        sys.exit(0)

