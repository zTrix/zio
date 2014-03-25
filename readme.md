
# zio

[![Build Status](https://travis-ci.org/zTrix/zio.png)](https://travis-ci.org/zTrix/zio)

[![endorse](http://api.coderwall.com/ztrix/endorsecount.png)](http://coderwall.com/ztrix)

[![Bitdeli Badge](https://d2weczhvl823v0.cloudfront.net/zTrix/zio/trend.png)](https://bitdeli.com/free "Bitdeli Badge")

[zio](https://github.com/zTrix/zio) is an easy-to-use io library for pwning development, supporting an unified interface for local process pwning and remote tcp socket io

## Examples
    
    from zio import *
    io = zio('vim')
    io.interact()

## Document

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

## TODO

 - add attach_gdb function
