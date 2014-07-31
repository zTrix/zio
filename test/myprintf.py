#!/usr/bin/env python2

import os, sys

def evals(s):
    st = 0      # 0 for normal, 1 for escape, 2 for \xXX
    ret = []
    i = 0
    while i < len(s):
        if st == 0:
            if s[i] == '\\':
                st = 1
            else:
                ret.append(s[i])
        elif st == 1:
            if s[i] in ('"', "'", "\\", "t", "n", "r"):
                if s[i] == 't':
                    ret.append('\t')
                elif s[i] == 'n':
                    ret.append('\n')
                elif s[i] == 'r':
                    ret.append('\r')
                else:
                    ret.append(s[i])
                st = 0
            elif s[i] == 'x':
                st = 2
            else:
                raise Exception('invalid repr of str %s' % s)
        else:
            num = int(s[i:i+2], 16)
            assert 0 <= num < 256
            ret.append(chr(num))
            st = 0
            i += 1
        i += 1
    return ''.join(ret)

sys.stdout.write(evals(sys.argv[1]))
sys.stdout.flush()
