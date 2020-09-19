import threading
import socket
import unittest
from zio import *

class ServerSock(threading.Thread):
    def __init__(self, addr=None, port=None):
        threading.Thread.__init__(self, name='ServerSock')
        self.addr = addr or '127.0.0.1'
        self.port = port or 9527

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

    def test_socket_io(self):
        server = ServerSock()
        server.start()

        io = zio(server.target_addr())

        content = io.read(5)
        self.assertEqual(content, b'hello')

        content = io.read(1)
        self.assertEqual(content, b' ')

        content = io.read(5)
        self.assertEqual(content, b'world')

        io.close()

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
