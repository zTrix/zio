#!/usr/bin/env python

# a minimal version socket-only zio which guaranteed to work for python2/3 on Linux/Mac and even for windows
from telnetlib import Telnet
import socket

class zio:
    def __init__(self, target):
        self.io = socket.create_connection(target)

    def read_until(self, pattern):
        if not pattern:
            return b''
        data = b''
        while True:
            c = self.io.recv(1)
            if not c:
                raise ValueError('pattern not found, buffer = %s' % data)

            data += c
            if pattern in data:
                return data

    def read(self, n=None):
        is_read_all = n == -1 or n is None
        data = b''
        while True:
            num = 1024 if is_read_all else n-len(data)
            c = self.io.recv(num)
            if not c:
                break
            data += c
            if len(data) == n:
                break
        return data

    def read_line(self):
        return self.read_until(b'\n')

    readline = read_line

    def write(self, data):
        self.io.sendall(data)

    def write_line(self, data):
        self.io.sendall(data + b'\n')

    writeline = write_line

    def interact(self):
        t = Telnet()
        t.sock = self.io
        t.interact()

    def close(self):
        self.io.close()

if __name__ == '__main__':
    print('''
# This is a minimal version socket-only io which guaranteed to work for python2/3 on Linux/Mac and even for windows
# example usage
from mini_zio import *

io = zio(('target', 1234))
banner = io.read_line()

io.read_until(b'username:')
io.write_line(b'admin')

io.interact()
io.close()
''')

