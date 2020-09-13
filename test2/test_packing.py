
import unittest
from zio import *

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

        with self.assertRaises(ValueError):
            b32('\x00\x00\x00\x00\x01\x00\x00\x00\x02')

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
