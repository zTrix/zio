
# zio

[![Build Status](https://travis-ci.org/zTrix/zio.png)](https://travis-ci.org/zTrix/zio)

[![endorse](http://api.coderwall.com/ztrix/endorsecount.png)](http://coderwall.com/ztrix)

`zio` is an expect-like io library, modified from [pexpect](https://github.com/pexpect/pexpect).

## Examples
    
    from zio import *
    io = zio('vim')
    io.interact()
