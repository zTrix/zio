#!/usr/bin/env python2

import os, sys, unittest, string, time, random, subprocess, random, socket
from zio import *

class Test(unittest.TestCase):

    def setUp(self):
        pass

    def exec_script(self, script, *args, **kwargs):
        from zio import which
        py = which('python2') or which('python')
        self.assertNotEqual(py, None)
        return self.cmdline(' '.join([py, '-u', os.path.join(os.path.dirname(sys.argv[0]), script)] + list(args)), **kwargs)

    def cmdline(self, cmd, **kwargs):
        print ''
        socat_exec = ',pty,stderr,ctty'
        if 'socat_exec' in kwargs:
            socat_exec = kwargs['socat_exec']
            del kwargs['socat_exec']
        io = zio(cmd, **kwargs)
        yield io
        io.close()
        print '"%s" exited: ' % cmd, io.exit_code
    
        for _ in range(16):
            port = random.randint(31337, 65530)
            p = subprocess.Popen(['socat', 'TCP-LISTEN:%d' % port, 'exec:"' + cmd + '"' + socat_exec])
            time.sleep(0.2)
            if p.returncode:
                continue
            try:
                io = zio(('127.0.0.1', port), **kwargs)
                yield io
            except socket.error:
                continue
            io.close()
            p.terminate()
            p.wait()
            break

    def test_tty(self):
        print ''
        io = zio('tty')
        out = io.read()
        self.assertEqual(out.strip(), 'not a tty', repr(out))

        io = zio('tty', stdin = TTY)
        out = io.read()
        self.assertTrue(out.strip().startswith('/dev/'), repr(out))

    def test_attach_socket(self):
        print ''
        for _ in range(4):
            port = random.randint(31337, 65530)
            p = subprocess.Popen(['socat', 'TCP-LISTEN:%d,crlf' % port, 'SYSTEM:"echo HTTP/1.0 200; echo Content-Type\: text/plain; echo; echo Hello, zio;"'])
            time.sleep(0.2)
            if p.returncode:
                continue
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(('127.0.0.1', port))
                line = ''
                while True:
                    c = s.recv(1)
                    if not c:
                        break
                    else:
                        line += c
                    if line.find('\n') > -1:
                        break
                assert line.rstrip() == "HTTP/1.0 200", repr(line)

                io = zio(s)
                
                line = io.readline()
                self.assertEqual(line.rstrip(), "Content-Type: text/plain", repr(line))
                line = io.readline()
                line = io.readline()

                self.assertEqual(line.rstrip(), "Hello, zio", repr(line))
                
                io.end()
                io.close()
            except socket.error:
                continue
            p.terminate()
            for _ in range(10):
                r = p.poll()
                if r is not None: break
                time.sleep(0.2)
            else:
                try:
                    p.kill()
                except:
                    pass
            break

    def test_tty_raw_out(self):
        s = []
        ans = []
        for i in range(10):
            r = random.randint(0,1)
            s.append('%d%s' % (i, r and '\\r\\n' or '\\n'))
            ans.append('%d%s' % (i, r and '\r\n' or '\n'))
        ans = ''.join(ans)
        cmd = "printf '" + ''.join(s) + "'"
        io = zio(cmd, stdout = TTY_RAW)
        rd = io.read()
        io.close()
        self.assertEqual(rd, ans)

        unprintable = [chr(c) for c in range(256) if chr(c) not in string.printable]
        for i in range(10):
            random.shuffle(unprintable)

        from zio import which
        py = which('python2') or which('python')
        self.assertNotEqual(py, None)
        io = zio(' '.join([py, '-u', os.path.join(os.path.dirname(sys.argv[0]), 'myprintf.py'), "'\\r\\n" + repr(''.join(unprintable))[1:-1] + "\\n'"]), stdout = TTY_RAW, print_read = COLORED(REPR))
        rd = io.read()
        self.assertEqual(rd, "\r\n" + ''.join(unprintable) + "\n")

    def test_pipe_out(self):
        io = zio('uname', stdout = PIPE)
        r = io.read()
        io.close()
        self.assertEqual(r.strip(), os.uname()[0])
        
    # ---- below are tests for both socket and process IO
    
    def test_uname(self):
        for io in self.cmdline('uname'):
            rs = io.read()
            self.assertEqual(rs.strip(), os.uname()[0], repr(rs))

    def test_cat(self):
        for io in self.cmdline('cat'):
            s = 'The Cat is #1\n'
            io.write(s)
            rs = io.readline()
            self.assertEqual(rs.strip(), s.strip(), 'TestCase Failure: got ' + repr(rs))

    def test_cat_eof(self):
        for io in self.cmdline('cat'):
            s = 'The Cat is #1'
            io.write(s)
            io.end()
            rs = io.read()
            self.assertEqual(rs.strip(), s.strip(), repr(rs))

    def test_cat_readline(self):
        for io in self.cmdline('cat'):
            s = 'The Cat is #1'
            io.write(s + '\n' + 'blah blah')
            rs = io.readline()
            self.assertEqual(rs.strip(), s)

    def test_read_until(self):
        for io in self.cmdline('cat'):
            s = ''.join([random.choice(string.printable[:62]) for x in range(1000)])
            io.writeline(s)
            io.read(100)
            io.read_until(s[500:600])
            mid = io.read(100)
            self.assertEqual(mid, s[600:700])

    def test_get_pass(self):
        # here we have to use TTY, or password won't get write thru
        # if you use subprocess, you will encouter same effect 
        for io in self.exec_script('userpass.py', stdin = TTY):
            io.read_until('Welcome')
            io.readline()
            io.read_until('Username: ')
            io.writeline('user')
            io.read_until('Password: ')   # note the 'stream = sys.stdout' line in userpass.py, which makes this prompt readable here, else Password will be echoed back from stdin(tty), not stdout, so you will never read this!!
            io.writeline('pass')
            io.readline()
            line = io.readline()
            self.assertEqual(line.strip(), 'Logged in', repr(line))
            io.end()

    def test_xxd(self):
        for io in self.cmdline('xxd', print_write = COLORED(REPR), print_read = COLORED(RAW, 'yellow'), socat_exec = ''):
            io.write(''.join([chr(x) for x in range(0, 256)]) + '\n')
            io.end()
            out = io.read()
            expected = '0000000: 0001 0203 0405 0607 0809 0a0b 0c0d 0e0f  ................\n0000010: 1011 1213 1415 1617 1819 1a1b 1c1d 1e1f  ................\n0000020: 2021 2223 2425 2627 2829 2a2b 2c2d 2e2f   !"#$%&\'()*+,-./\n0000030: 3031 3233 3435 3637 3839 3a3b 3c3d 3e3f  0123456789:;<=>?\n0000040: 4041 4243 4445 4647 4849 4a4b 4c4d 4e4f  @ABCDEFGHIJKLMNO\n0000050: 5051 5253 5455 5657 5859 5a5b 5c5d 5e5f  PQRSTUVWXYZ[\\]^_\n0000060: 6061 6263 6465 6667 6869 6a6b 6c6d 6e6f  `abcdefghijklmno\n0000070: 7071 7273 7475 7677 7879 7a7b 7c7d 7e7f  pqrstuvwxyz{|}~.\n0000080: 8081 8283 8485 8687 8889 8a8b 8c8d 8e8f  ................\n0000090: 9091 9293 9495 9697 9899 9a9b 9c9d 9e9f  ................\n00000a0: a0a1 a2a3 a4a5 a6a7 a8a9 aaab acad aeaf  ................\n00000b0: b0b1 b2b3 b4b5 b6b7 b8b9 babb bcbd bebf  ................\n00000c0: c0c1 c2c3 c4c5 c6c7 c8c9 cacb cccd cecf  ................\n00000d0: d0d1 d2d3 d4d5 d6d7 d8d9 dadb dcdd dedf  ................\n00000e0: e0e1 e2e3 e4e5 e6e7 e8e9 eaeb eced eeef  ................\n00000f0: f0f1 f2f3 f4f5 f6f7 f8f9 fafb fcfd feff  ................\n0000100: 0a                                       .\n'
            self.assertEqual(out.replace('\r\n', '\n'), expected, repr(out))
        
if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(Test)

    tests = []

    if len(sys.argv) > 1:
        tests.extend(sys.argv[1:])

    if len(tests):
        suite = unittest.TestSuite(map(Test, tests))

    rs = unittest.TextTestRunner(verbosity = 2).run(suite)
    if len(rs.errors) > 0 or len(rs.failures) > 0:
        sys.exit(10)
    else:
        sys.exit(0)

