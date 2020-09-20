from __future__ import print_function

import os
import sys
import random
import threading
import socket
import time
import subprocess
from zio import *

port_used = set()

class EchoServer(threading.Thread):
    def __init__(self, addr=None, port=None, content=b'', sleep_before=None, sleep_after=None, sleep_between=None):
        threading.Thread.__init__(self, name='ServerSock')
        self.addr = addr or '127.0.0.1'
        global port_used
        while True:
            if port is None or port in port_used:
                port = random.choice(range(50000, 60000))
            else:
                break
        self.port = port
        self.content = content
        self.sleep_before = sleep_before
        self.sleep_after = sleep_after
        self.sleep_between = sleep_between
        self.setDaemon(True)

    def run(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind((self.addr, self.port))
        server_sock.listen(1)

        peer_sock, _peer_addr = server_sock.accept()

        contents = self.content if isinstance(self.content, (list, tuple)) else [self.content]

        if self.sleep_before:
            time.sleep(self.sleep_before)

        try:
            for item in contents:
                peer_sock.sendall(item)
                
                if self.sleep_between:
                    time.sleep(self.sleep_between)
            
            if self.sleep_after:
                time.sleep(self.sleep_after)
        except:
            pass
        finally:
            peer_sock.close()
            server_sock.close()

    def target_addr(self):
        return (self.addr, self.port)

def exec_cmdline(cmd, **kwargs):
    print('')
    socat_exec = ',pty,stderr,ctty'
    if 'socat_exec' in kwargs:
        socat_exec = kwargs['socat_exec']
        del kwargs['socat_exec']
    io = zio(cmd, **kwargs)
    yield io
    io.close()
    print('%r exited: %s' % (cmd, io.exit_status()))

    for _ in range(16):
        port = random.randint(31337, 65530)
        p = subprocess.Popen(['socat', 'TCP-LISTEN:%d' % port, 'exec:"' + cmd + '"' + socat_exec])
        time.sleep(0.2)
        if p.returncode:
            continue
        try:
            io = zio(('127.0.0.1', port), **kwargs)
            yield io
        except socket.error:
            continue
        io.close()
        p.terminate()
        p.wait()
        break

def exec_script(script, *args, **kwargs):
    py = sys.executable
    return cmdline(' '.join([py, '-u', os.path.join(os.path.dirname(sys.argv[0]), script)] + list(args)), **kwargs)
