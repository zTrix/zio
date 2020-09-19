
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

        self.assertIn(REPR(b'asdf'), "b'asdf'\r\n", 'b"asdf"\r\n')

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
