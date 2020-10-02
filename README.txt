
zio
====

`zio <https://github.com/zTrix/zio>`_ is an easy-to-use io library for pwning development, supporting an unified interface for local process pwning and TCP socket io.

The primary goal of `zio <https://github.com/zTrix/zio>`_ is to provide unified io interface between process stdin/stdout and TCP socket io. So when you have done local pwning development, you only need to change the io target to pwn the remote server.

The following code illustrate the basic idea.

.. code:: python

    from zio import *

    debug_local = True

    if debug_local:
        io = zio('./buggy-server')            # used for local pwning development
    elif you_are_pwning_remote_server:
        io = zio(('1.2.3.4', 1337))           # used to exploit remote service

    io.read_until(b'Welcome banner')
    io.write(your_awesome_ropchain_or_shellcode)
    # hey, we got an interactive shell!
    io.interact()

License
=======

`zio <https://github.com/zTrix/zio>`_ use `SATA License (Star And Thank Author License) <https://github.com/zTrix/sata-license>`_, so you have to star this project before using. Read the LICENSE.txt carefully.


Installation
============

This is a single-file project so in most cases you can just download `zio.py <https://raw.githubusercontent.com/zTrix/zio/master/zio.py>`_ and start using.

pip is also supported, so you can also install by running 

.. code:: bash

    $ pip install zio

More Info
=========

Goto `zio <https://github.com/zTrix/zio>` for more information.
