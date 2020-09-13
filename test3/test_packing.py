
import zio

assert zio.l32(0) == b'\x00\x00\x00\x00'
assert zio.b32(1) == b'\x00\x00\x00\x01'
assert zio.l16(0x35) == b'\x35\x00'
assert zio.l32(b'\x83\x06\x40\x00') == 0x400683
assert zio.l64(b'\x83\x06\x40', autopad=True) == 0x400683
assert zio.b16(b'\x23', autopad=True) == 0x23
assert zio.b32(b'\x12\x34', autopad=True) == 0x1234
