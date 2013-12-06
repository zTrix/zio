#!/usr/bin/env python2

import os, sys, unittest, string, time, random
from zio import *

class Test(unittest.TestCase):

    def setUp(self):
        pass
    
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

    def test_cat_ctrl_c(self):
        print ''
        io = zio('cat')
        s = 'The Cat is #1\n'
        io.write(s)
        io.writecontrol('c')
        rs = io.read()
        self.assertEqual(rs.strip(), s.strip(), repr(rs))
        io.close()

    def test_readline(self):
        print ''
        io = zio('cat')
        s = 'The Cat is #1'
        io.write(s + '\n' + 'blah blah')
        rs = io.readline()
        self.assertEqual(rs.strip(), s)
        io.close()

    def test_cat_eof(self):
        print ''
        io = zio('cat')
        s = 'The Cat is #1'
        io.writeline(s)
        io.writeeof()
        rs = io.read()
        self.assertEqual(rs.strip(), s.strip(), repr(rs))
        io.close()

    def test_cat_eof2(self):
        print ''
        io = zio('cat')
        s = 'The Cat is #1'
        io.write(s)
        # you need to press Ctrl-D twice if not at new line
        io.writeeof()
        io.writeeof()
        rs = io.read()
        self.assertEqual(rs.strip(), s.strip(), repr(rs))
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
        f = open('/tmp/_test_getpass_zio.py', 'w')
        f.write("\nimport getpass\n\nprint 'Welcome'\n\na = getpass.getpass('Password:')\n\nif a == 'pass':\n    print 'Logged in'\nelse:\n    print 'Invalid'\n\n")
        f.close()
        io = zio('python2 /tmp/_test_getpass_zio.py')
        io.read_until('Welcome\r\n')
        io.writeline('pass')
        line = io.readline()
        self.assertEqual(line.strip(), 'Logged in', repr(line))

    def test_http(self):
        io = zio(('ifconfig.me', 80))
        io.write('GET / HTTP/1.1\r\nHOST: ifconfig.me\r\nUser-Agent: curl\r\n\r\n')
        self.assertEqual(io.read(5), 'HTTP/', 'bad http line')
        self.assertEqual(io.readline().strip(), '1.1 200 OK', 'bad http line')
        io.close()
        
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

