#!/usr/bin/env python2
#-*- coding:utf-8 -*-

import os, sys, termios

flags = {
    'iflags' : 'IGNBRK BRKINT IGNPAR PARMRK INPCK ISTRIP INLCR IGNCR ICRNL IUCLC IXON IXANY IXOFF IMAXBEL IUTF8'.split(' '),
    'oflags' : 'OPOST OLCUC ONLCR OCRNL ONOCR ONLRET OFILL OFDEL NLDLY CRDLY TABDLY BSDLY VTDLY FFDLY'.split(' '),
    'cflags' : 'CBAUD CBAUDEX CSIZE CSTOPB CREAD PARENB PARODD HUPCL CLOCAL LOBLK CIBAUD CMSPAR CRTSCTS'.split(' '),
    'lflags' : 'ISIG ICANON XCASE ECHO ECHOE ECHOK ECHONL ECHOCTL ECHOPRT ECHOKE DEFECHO FLUSHO NOFLSH TOSTOP PENDIN IEXTEN'.split(' '),
}

mode = int(sys.argv[2])

for f in flags[sys.argv[1]]:
    try:
        if getattr(termios, f) & mode:
            print f
    except:
        pass
