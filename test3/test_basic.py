#!/usr/bin/env python3
import random
import threading
import socket
import unittest
from io import StringIO
from zio import *

class ServerSock(threading.Thread):
    def __init__(self, addr=None, port=None):
        threading.Thread.__init__(self, name='ServerSock')
        self.addr = addr or '127.0.0.1'
        self.port = port or random.choice(range(9527, 10000))
        self.setDaemon(True)

    def run(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind((self.addr, self.port))
        server_sock.listen(1)

        peer_sock, peer_addr = server_sock.accept()
        peer_sock.sendall(b'hello world\n')
        peer_sock.sendall(b'\x81\x33\x80\xff\xff\x7f\x00\x00\x00\n')
        peer_sock.close()

    def target_addr(self):
        return (self.addr, self.port)

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

        self.assertIn(REPR(b'asdf'), "b'asdf'\r\n", 'b"asdf"\r\n')

    def test_socket_io(self):
        server = ServerSock()
        server.start()

        logfile = StringIO()

        io = zio(server.target_addr(), logfile=logfile, print_read=True, print_write=False)

        content = io.read(5)
        self.assertEqual(content, b'hello')
        self.assertEqual(logfile.getvalue(), 'hello')

        content = io.read(1)
        self.assertEqual(content, b' ')

        content = io.read(5)
        self.assertEqual(content, b'world')

        self.assertEqual(logfile.getvalue(), 'hello world')

        io.close()

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
