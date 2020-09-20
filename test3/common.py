import random
import threading
import socket
import time

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

        peer_sock, peer_addr = server_sock.accept()

        contents = self.content if isinstance(self.content, (list, tuple)) else [self.content]

        if self.sleep_before:
            time.sleep(self.sleep_before)

        for item in contents:
            peer_sock.sendall(item)
            
            if self.sleep_between:
                time.sleep(self.sleep_between)
        
        if self.sleep_after:
            time.sleep(self.sleep_after)

        peer_sock.close()
        server_sock.close()

    def target_addr(self):
        return (self.addr, self.port)
