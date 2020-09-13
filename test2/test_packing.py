
from zio import *

assert l32(0) == '\x00\x00\x00\x00'
assert b32(1) == '\x00\x00\x00\x01'
assert l16(0x35) == '\x35\x00'
assert l32('\x83\x06\x40\x00') == 0x400683
assert l64(b'\x83\x06\x40', autopad=True) == 0x400683
assert b16(b'\x23', autopad=True) == 0x23
assert b32(b'\x12\x34', autopad=True) == 0x1234
assert l32([0, 1, 2]) == b'\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00'
assert l32(b'\x00\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00') == [0, 1, 2]
assert l32(b'\x00\x00\x00\x00\x01\x00\x00\x00\x02', autopad=True) == [0, 1, 2]
assert b32(b'\x00\x00\x00\x00\x01\x00\x00\x00\x02', autopad=True) == [0, 0x1000000, 2]
