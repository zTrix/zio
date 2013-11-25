#!/usr/bin/env python2

import os, sys, unittest, string, time, random
from zio import *

class Test(unittest.TestCase):

    def setUp(self):
        pass
    
    def test_read(self):
        print ''
        io = zio('uname')
        rs = io.read()
        io.join()
        # print 'test_read', repr(rs)
        self.assertEqual(rs.strip(), os.uname()[0])

    def test_read_cat(self):
        print ''
        io = zio('cat')
        s = 'The Cat is #1'
        io.write(s)
        io.close()
        rs = io.read()
        self.assertEqual(rs, s)

    def test_read_line(self):
        print ''
        io = zio('cat')
        s = 'The Cat is #1'
        io.write(s + '\n' + 'blah blah')
        io.close()
        rs = io.readline()
        self.assertEqual(rs.strip(), s)

    def test_read_until(self):
        print ''
        io = zio('cat')
        s = ''.join([random.choice(string.printable[:62]) for x in range(1000)])
        io.write(s)
        io.read(100)
        io.read_until(s[500:600])
        mid = io.read(100)
        self.assertEqual(mid, s[600:700])
        

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(Test)

    tests = ['test_read_until']
    # suite = unittest.TestSuite(map(Test, tests))

    rs = unittest.TextTestRunner(verbosity = 2).run(suite)
    if len(rs.errors) > 0 or len(rs.failures) > 0:
        sys.exit(10)
    else:
        sys.exit(0)

