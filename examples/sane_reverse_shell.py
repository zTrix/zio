#!/usr/bin/env python3

from zio import *

# spawn a sane reverse shell using following command
# socat tcp-l:9999,reuseaddr,fork exec:'bash -li',pty,stderr,setsid,sigint,sane

io = zio(('127.0.0.1', 9999), timeout=99999)

io.interact(raw_mode=True)
