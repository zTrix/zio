
# zio

[![Build Status](https://travis-ci.org/zTrix/zio.png)](https://travis-ci.org/zTrix/zio)

[![endorse](http://api.coderwall.com/ztrix/endorsecount.png)](http://coderwall.com/ztrix)

[![Bitdeli Badge](https://d2weczhvl823v0.cloudfront.net/zTrix/zio/trend.png)](https://bitdeli.com/free "Bitdeli Badge")

`zio` is an expect-like io library, modified from [pexpect](https://github.com/pexpect/pexpect).

## Examples
    
    from zio import *
    io = zio('vim')
    io.interact()

## Document

### about line break

Just don't read '\n' or '\r', use readline() instead

## TODO

 - add attach_gdb function
 - handle Ctrl-V Ctrl-C signal
 - raw mode
