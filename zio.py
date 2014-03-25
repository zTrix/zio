#!/usr/bin/env python2

import struct, socket, os, sys, subprocess, threading, pty, time, re, select, termios, resource, tty, errno, signal, fcntl, gc, platform
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    from termcolor import colored
except:
    def colored(text, color=None, on_color=None, attrs=None):
        return text

__ALL__ = ['stdout', 'log', 'l16', 'b16', 'l32', 'b32', 'l64', 'b64', 'zio', 'EOF', 'TIMEOUT', 'SOCKET', 'PROCESS', 'REPR', 'HEX', 'EVAL', 'UNHEX', 'RAW', 'NONE', 'COLORED', 'PIPE', 'TTY']

def stdout(s, color = None, on_color = None, attrs = None):
    if not color:
        sys.stdout.write(s)
    else:
        sys.stdout.write(colored(s, color, on_color, attrs))
    sys.stdout.flush()

def log(s, color = None, on_color = None, attrs = None, new_line = True):
    if not color:
        print >> sys.stderr, str(s),
    else:
        print >> sys.stderr, colored(str(s), color, on_color, attrs),
    if new_line:
        sys.stderr.write('\n')
    sys.stderr.flush()

def l16(i): return isinstance(i, (int, long)) and struct.pack('<H', i % (1<<16)) or struct.unpack('<H', i)[0]
def b16(i): return isinstance(i, (int, long)) and struct.pack('>H', i % (1<<16)) or struct.unpack('>H', i)[0]
def l32(i): return isinstance(i, (int, long)) and struct.pack('<I', i % (1<<32)) or struct.unpack('<I', i)[0]
def b32(i): return isinstance(i, (int, long)) and struct.pack('>I', i % (1<<32)) or struct.unpack('>I', i)[0]
def l64(i): return isinstance(i, (int, long)) and struct.pack('<Q', i % (1<<64)) or struct.unpack('<Q', i)[0]
def b64(i): return isinstance(i, (int, long)) and struct.pack('>Q', i % (1<<64)) or struct.unpack('>Q', i)[0]

class EOF(Exception):
    """Raised when EOF is read from child or socket.
    This usually means the child has exited or socket shutdown at remote end"""

class TIMEOUT(Exception):
    """Raised when a read timeout exceeds the timeout. """

SOCKET = 'socket'
PROCESS = 'process'
PIPE = 'PIPE'
TTY = 'tty'

def COLORED(f, color = 'cyan', on_color = None, attrs = None): return lambda s : colored(f(s), color, on_color, attrs)
def REPR(s): return repr(str(s)) + '\r\n'
def EVAL(s): return eval(s)     # don't pwn yourself!!!
def HEX(s): return str(s).encode('hex') + '\r\n'
def UNHEX(s): return s.decode('hex')
def RAW(s): return str(s)
def NONE(s): return ''

class zio(object):

    # TODO: logfile support ?
    def __init__(self, target, stdin = PIPE, stdout = TTY, print_read = RAW, print_write = RAW, timeout = 8, cwd = None, env = None, sighup = signal.SIG_IGN, write_delay = 0.05, ignorecase = False):
        """
        zio is an easy-to-use io library for pwning development, supporting an unified interface for local process pwning and remote tcp socket io

        example:

        io = zio(('localhost', 80))
        io = zio('ls -l')
        io = zio(['ls', '-l'])

        params:
            print_read = bool, if true, print all the data read from target
            print_write = bool, if true, print all the data sent out
        """

        if not target:
            raise Exception('cmdline or socket not provided for zio, try zio("ls -l")')

        self.target = target
        self.print_read = print_read
        self.print_write = print_write
        if self.print_read == True: self.print_read = RAW
        if self.print_read == False: self.print_read = NONE
        if self.print_write == True: self.print_write = RAW
        if self.print_write == False: self.print_write = NONE
        assert not self.print_read or callable(self.print_read)
        assert not self.print_write or callable(self.print_write)

        if isinstance(timeout, (int, long)) and timeout > 0:
            self.timeout = timeout
        else:
            self.timeout = 8

        self.wfd = -1          # the fd to write to
        self.rfd = -1           # the fd to read from
        
        self.write_delay = write_delay     # the delay before writing data, pexcept said Linux don't like this to be below 30ms
        self.close_delay = 0.1      # like pexcept, will used by close(), to give kernel time to update process status, time in seconds
        self.terminate_delay = 0.1  # like close_delay
        self.cwd = cwd
        self.env = env
        self.sighup = sighup
     
        self.flag_eof = False
        self.closed = True
        self.exit_code = None

        self.ignorecase = ignorecase

        self.buffer = str()

        if self.mode() == SOCKET:
            self.sock = socket.create_connection(self.target, self.timeout)
            self.name = '<socket ' + self.target[0] + ':' + str(self.target[1]) + '>'
            self.rfd = self.wfd = self.sock.fileno()
            self.closed = False
            return

        # spawn process below
        self.pid = None

        self.closed = False

        if isinstance(target, type('')):
            self.args = split_command_line(target)
            self.command = self.args[0]
        else:
            self.args = target
            self.command = self.args[0]

        command_with_path = which(self.command)
        if command_with_path is None:
            raise Exception('Command not found in path: %s' % self.command)

        self.command = command_with_path
        self.args[0] = self.command
        self.name = '<' + ' '.join(self.args) + '>'

        assert self.pid is None, 'pid must be None, to prevent double spawn'
        assert self.command is not None, 'The command to be spawn must not be None'

        stdout_master_fd, stdout_slave_fd = stdout == TTY and pty.openpty() or self.pipe_cloexec()
        if stdout_master_fd < 0 or stdout_slave_fd < 0: raise Exception('Could not openpty for stdout/stderr')

        # use another pty for stdin because we don't want our input to be echoed back in stdout
        # set echo off does not help because in application like ssh, when you input the password
        # echo will be switched on again
        # and dont use os.pipe either, because many thing weired will happen, such as baskspace not working, ssh lftp command hang

        stdin_master_fd, stdin_slave_fd = stdin == TTY and pty.openpty() or self.pipe_cloexec()
        if stdin_master_fd < 0 or stdin_slave_fd < 0: raise Exception('Could not openpty for stdin')

        gc_enabled = gc.isenabled()
        # Disable gc to avoid bug where gc -> file_dealloc ->
        # write to stderr -> hang.  http://bugs.python.org/issue1336
        gc.disable()
        try:
            self.pid = os.fork()
        except:
            if gc_enabled:
                gc.enable()
            raise

        if self.pid < 0:
            raise Exception('failed to fork')
        elif self.pid == 0:     # Child
            os.close(stdout_master_fd)
            
            if os.isatty(stdin_slave_fd):
                self.__pty_make_controlling_tty(stdin_slave_fd)
                # self.__pty_make_controlling_tty(stdout_slave_fd)

            try:
                if os.isatty(stdout_slave_fd) and os.isatty(pty.STDIN_FILENO):
                    h, w = self.getwinsize(0)
                    self.setwinsize(stdout_slave_fd, h, w)     # note that this may not be successful
            except BaseException, ex:
                # TODO: write log in current directory
                # if self.print_log: log('[ WARN ] setwinsize exception: %s' % (str(ex)), 'yellow')
                pass

            # Dup fds for child
            def _dup2(a, b):
                # dup2() removes the CLOEXEC flag but
                # we must do it ourselves if dup2()
                # would be a no-op (issue #10806).
                if a == b:
                    self._set_cloexec_flag(a, False)
                elif a is not None:
                    os.dup2(a, b)

            # redirect stdout and stderr to pty
            os.dup2(stdout_slave_fd, pty.STDOUT_FILENO)
            os.dup2(stdout_slave_fd, pty.STDERR_FILENO)

            # redirect stdin to stdin_slave_fd instead of stdout_slave_fd, to prevent input echoed back
            _dup2(stdin_slave_fd, pty.STDIN_FILENO)

            if stdout_slave_fd > 2:
                os.close(stdout_slave_fd)

            if stdin_master_fd is not None:
                os.close(stdin_master_fd)

            # do not allow child to inherit open file descriptors from parent

            max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
            os.closerange(3, max_fd)

            if self.sighup:         # persist after parent process exits
                signal.signal(signal.SIGHUP, self.sighup)

            if self.cwd is not None:
                os.chdir(self.cwd)

            if self.env is None:
                os.execv(self.command, self.args)
            else:
                os.execvpe(self.command, self.args, self.env)
            
            # TODO: add subprocess errpipe to detect child error
            # child exit here, the same as subprocess module do
            os._exit(255)

        else:
            # after fork, parent
            self.wfd = stdin_master_fd

            if os.isatty(self.wfd):
                # there is no way to eliminate controlling characters in tcattr
                # so we have to set raw mode here now
                self._wfd_init_mode = tty.tcgetattr(self.wfd)[:]
                self.ttyraw(self.wfd)
                self._wfd_raw_mode = tty.tcgetattr(self.wfd)[:]

            os.close(stdin_slave_fd)
            self.rfd = stdout_master_fd
            os.close(stdout_slave_fd)
            if gc_enabled:
                gc.enable()

            time.sleep(self.close_delay)

    def __pty_make_controlling_tty(self, tty_fd):
        '''This makes the pseudo-terminal the controlling tty. This should be
        more portable than the pty.fork() function. Specifically, this should
        work on Solaris. '''

        child_name = os.ttyname(tty_fd)

        # Disconnect from controlling tty. Harmless if not already connected.
        try:
            fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
            if fd >= 0:
                os.close(fd)
        # which exception, shouldnt' we catch explicitly .. ?
        except:
            # Already disconnected. This happens if running inside cron.
            pass

        os.setsid()

        # Verify we are disconnected from controlling tty
        # by attempting to open it again.
        try:
            fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
            if fd >= 0:
                os.close(fd)
                raise Exception('Failed to disconnect from ' +
                    'controlling tty. It is still possible to open /dev/tty.')
        # which exception, shouldnt' we catch explicitly .. ?
        except:
            # Good! We are disconnected from a controlling tty.
            pass

        # Verify we can open child pty.
        fd = os.open(child_name, os.O_RDWR)
        if fd < 0:
            raise Exception("Could not open child pty, " + child_name)
        else:
            os.close(fd)

        # Verify we now have a controlling tty.
        fd = os.open("/dev/tty", os.O_WRONLY)
        if fd < 0:
            raise Exception("Could not open controlling tty, /dev/tty")
        else:
            os.close(fd)

    def _set_cloexec_flag(self, fd, cloexec=True):
        try:
            cloexec_flag = fcntl.FD_CLOEXEC
        except AttributeError:
            cloexec_flag = 1

        old = fcntl.fcntl(fd, fcntl.F_GETFD)
        if cloexec:
            fcntl.fcntl(fd, fcntl.F_SETFD, old | cloexec_flag)
        else:
            fcntl.fcntl(fd, fcntl.F_SETFD, old & ~cloexec_flag)

    def pipe_cloexec(self):
        """Create a pipe with FDs set CLOEXEC."""
        # Pipes' FDs are set CLOEXEC by default because we don't want them
        # to be inherited by other subprocesses: the CLOEXEC flag is removed
        # from the child's FDs by _dup2(), between fork() and exec().
        # This is not atomic: we would need the pipe2() syscall for that.
        r, w = os.pipe()
        self._set_cloexec_flag(r)
        self._set_cloexec_flag(w)
        return w, r

    def fileno(self):
        '''This returns the file descriptor of the pty for the child.
        '''
        if self.mode() == SOCKET:
            return self.sock.fileno()
        else:
            return self.rfd

    def setwinsize(self, fd, rows, cols):   # from pexpect, thanks!

        '''This sets the terminal window size of the child tty. This will cause
        a SIGWINCH signal to be sent to the child. This does not change the
        physical window size. It changes the size reported to TTY-aware
        applications like vi or curses -- applications that respond to the
        SIGWINCH signal. '''

        # Check for buggy platforms. Some Python versions on some platforms
        # (notably OSF1 Alpha and RedHat 7.1) truncate the value for
        # termios.TIOCSWINSZ. It is not clear why this happens.
        # These platforms don't seem to handle the signed int very well;
        # yet other platforms like OpenBSD have a large negative value for
        # TIOCSWINSZ and they don't have a truncate problem.
        # Newer versions of Linux have totally different values for TIOCSWINSZ.
        # Note that this fix is a hack.
        TIOCSWINSZ = getattr(termios, 'TIOCSWINSZ', -2146929561)
        if TIOCSWINSZ == 2148037735:
            # Same bits, but with sign.
            TIOCSWINSZ = -2146929561
        # Note, assume ws_xpixel and ws_ypixel are zero.
        s = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(fd, TIOCSWINSZ, s)

    def getwinsize(self, fd):

        '''This returns the terminal window size of the child tty. The return
        value is a tuple of (rows, cols). '''

        TIOCGWINSZ = getattr(termios, 'TIOCGWINSZ', 1074295912)
        s = struct.pack('HHHH', 0, 0, 0, 0)
        x = fcntl.ioctl(fd, TIOCGWINSZ, s)
        return struct.unpack('HHHH', x)[0:2]

    def __str__(self):
        ret = ['io-mode: %s' % self.mode(), 
               'name: %s' % self.name, 
               'timeout: %f' % self.timeout,
               'write-fd: %d' % (isinstance(self.wfd, (int, long)) and self.wfd or self.fileno()),
               'read-fd: %d' % (isinstance(self.rfd, (int, long)) and self.rfd or self.fileno()),
               'buffer(last 100 chars): %r' % (self.buffer[-100:]),
               'eof: %s' % self.flag_eof]
        if self.mode() == SOCKET:
            pass
        elif self.mode() == PROCESS:
            ret.append('command: %s' % str(self.command))
            ret.append('args: %r' % (self.args,))
            ret.append('write-delay: %f' % self.write_delay)
            ret.append('close-delay: %f' % self.close_delay)
        return '\n'.join(ret)

    def eof(self):

        '''This returns True if the EOF exception was ever raised.
        '''

        return self.flag_eof

    def terminate(self, force=False):

        '''This forces a child process to terminate. It starts nicely with
        SIGHUP and SIGINT. If "force" is True then moves onto SIGKILL. This
        returns True if the child was terminated. This returns False if the
        child could not be terminated. '''

        if self.mode() != PROCESS:
            # should I raise something?
            return

        if not self.isalive():
            return True
        try:
            self.kill(signal.SIGHUP)
            time.sleep(self.terminate_delay)
            if not self.isalive():
                return True
            self.kill(signal.SIGCONT)
            time.sleep(self.terminate_delay)
            if not self.isalive():
                return True
            self.kill(signal.SIGINT)        # SIGTERM is nearly identical to SIGINT
            time.sleep(self.terminate_delay)
            if not self.isalive():
                return True
            if force:
                self.kill(signal.SIGKILL)
                time.sleep(self.terminate_delay)
                if not self.isalive():
                    return True
                else:
                    return False
            return False
        except OSError:
            # I think there are kernel timing issues that sometimes cause
            # this to happen. I think isalive() reports True, but the
            # process is dead to the kernel.
            # Make one last attempt to see if the kernel is up to date.
            time.sleep(self.terminate_delay)
            if not self.isalive():
                return True
            else:
                return False

    def kill(self, sig):

        '''This sends the given signal to the child application. In keeping
        with UNIX tradition it has a misleading name. It does not necessarily
        kill the child unless you send the right signal. '''

        # Same as os.kill, but the pid is given for you.
        if self.isalive():
            os.kill(self.pid, sig)

    def wait(self):

        '''This waits until the child exits. This is a blocking call. This will
        not read any data from the child, so this will block forever if the
        child has unread output and has terminated. In other words, the child
        may have printed output then called exit(), but, the child is
        technically still alive until its output is read by the parent. '''

        if self.isalive():
            pid, status = os.waitpid(self.pid, 0)
        else:
            raise Exception('Cannot wait for dead child process.')
        self.exit_code = os.WEXITSTATUS(status)
        if os.WIFEXITED(status):
            self.exit_code = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            self.exit_code = os.WTERMSIG(status)
        elif os.WIFSTOPPED(status):
            # You can't call wait() on a child process in the stopped state.
            raise Exception('Called wait() on a stopped child ' +
                    'process. This is not supported. Is some other ' +
                    'process attempting job control with our child pid?')
        return self.exit_code

    def isalive(self):

        '''This tests if the child process is running or not. This is
        non-blocking. If the child was terminated then this will read the
        exit code or signalstatus of the child. This returns True if the child
        process appears to be running or False if not. It can take literally
        SECONDS for Solaris to return the right status. '''

        if self.mode() == SOCKET:
            return not self.flag_eof

        if self.exit_code is not None:
            return False

        if self.flag_eof:
            # This is for Linux, which requires the blocking form
            # of waitpid to # get status of a defunct process.
            # This is super-lame. The flag_eof would have been set
            # in read_nonblocking(), so this should be safe.
            waitpid_options = 0
        else:
            waitpid_options = os.WNOHANG

        try:
            pid, status = os.waitpid(self.pid, waitpid_options)
        except OSError:
            err = sys.exc_info()[1]
            # No child processes
            if err.errno == errno.ECHILD:
                raise Exception('isalive() encountered condition ' +
                        'where "terminated" is 0, but there was no child ' +
                        'process. Did someone else call waitpid() ' +
                        'on our process?')
            else:
                raise err

        # I have to do this twice for Solaris.
        # I can't even believe that I figured this out...
        # If waitpid() returns 0 it means that no child process
        # wishes to report, and the value of status is undefined.
        if pid == 0:
            try:
                ### os.WNOHANG) # Solaris!
                pid, status = os.waitpid(self.pid, waitpid_options)
            except OSError as e:
                # This should never happen...
                if e.errno == errno.ECHILD:
                    raise Exception('isalive() encountered condition ' +
                            'that should never happen. There was no child ' +
                            'process. Did someone else call waitpid() ' +
                            'on our process?')
                else:
                    raise

            # If pid is still 0 after two calls to waitpid() then the process
            # really is alive. This seems to work on all platforms, except for
            # Irix which seems to require a blocking call on waitpid or select,
            # so I let read_nonblocking take care of this situation
            # (unfortunately, this requires waiting through the timeout).
            if pid == 0:
                return True

        if pid == 0:
            return True

        if os.WIFEXITED(status):
            self.exit_code = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            self.exit_code = os.WTERMSIG(status)
        elif os.WIFSTOPPED(status):
            raise Exception('isalive() encountered condition ' +
                    'where child process is stopped. This is not ' +
                    'supported. Is some other process attempting ' +
                    'job control with our child pid?')
        return False

    def interact(self, escape_character=chr(29), input_filter = None, output_filter = None):
        """
        when stdin is passed using os.pipe, backspace key will not work as expected, 
        if wfd is not a tty, then when backspace pressed, I can see that 0x7f is passed, but vim does not delete backwards, so you should choose the right input when using zio
        """
        if self.mode() == SOCKET:
            while self.isalive():
                try:
                    r, w, e = self.__select([self.rfd, pty.STDIN_FILENO], [], [])
                except KeyboardInterrupt:
                    break
                if self.rfd in r:
                    try:
                        data = None
                        data = self._read(1024)
                        if data:
                            if output_filter: data = output_filter(data)
                            stdout(self.print_read(data))
                    except EOF:
                        self.flag_eof = True
                        break
                if pty.STDIN_FILENO in r:
                    try:
                        data = None
                        data = os.read(pty.STDIN_FILENO, 1024)
                    except OSError, e:
                        # the subprocess may have closed before we get to reading it
                        if e.errno != errno.EIO:
                            raise
                    if data is not None:
                        if input_filter: data = input_filter(data)
                        i = data.rfind(escape_character)
                        if i != -1: data = data[:i]
                        try:
                            while data != b'' and self.isalive():
                                n = self._write(data)
                                data = data[n:]
                            if i != -1:
                                break
                        except:         # write error, may be socket.error, Broken pipe
                            break
            return

        self.buffer = str()
        if os.isatty(pty.STDIN_FILENO):
            mode = tty.tcgetattr(pty.STDIN_FILENO)  # mode will be restored after interact
            tty.setraw(pty.STDIN_FILENO)        # set to raw mode to pass all input thru, supporting apps as vim
        # here, enable cooked mode for process stdin
        # but we should only enable for those who need cooked mode, not stuff like vim
        # we just do a simple detection here
        if os.isatty(self.wfd):
            wfd_mode = tty.tcgetattr(self.wfd)
            if wfd_mode == self._wfd_raw_mode:     # if untouched by forked child
                tty.tcsetattr(self.wfd, tty.TCSAFLUSH, self._wfd_init_mode)

        try:
            rfdlist = [self.rfd, pty.STDIN_FILENO]
            if os.isatty(self.wfd):
                # wfd for tty echo
                rfdlist.append(self.wfd)
            while self.isalive():
                r, w, e = self.__select(rfdlist, [], [])
                if self.wfd in r:          # handle tty echo back first if wfd is a tty
                    try:
                        data = None
                        data = os.read(self.wfd, 1024)
                    except OSError, e:
                        if e.errno != errno.EIO:
                            raise
                    if data is not None:
                        if output_filter: data = output_filter(data)
                        # already translated by tty, so don't wrap print_write anymore
                        stdout(data)
                if self.rfd in r:
                    try:
                        data = None
                        data = os.read(self.rfd, 1024)
                    except OSError, e:
                        if e.errno != errno.EIO:
                            raise
                    if data is not None:
                        if output_filter: data = output_filter(data)
                        stdout(self.print_read(data))
                if pty.STDIN_FILENO in r:
                    try:
                        data = None
                        data = os.read(pty.STDIN_FILENO, 1024)
                    except OSError, e:
                        # the subprocess may have closed before we get to reading it
                        if e.errno != errno.EIO:
                            raise
                    # in BSD, you can still read '' from rfd, so never use `data is not None` here
                    if data:
                        if input_filter: data = input_filter(data)
                        i = data.rfind(escape_character)
                        if i != -1: data = data[:i]
                        if not os.isatty(self.wfd):     # we must do the translation when tty does not help
                            data = data.replace('\r', '\n')
                            # also echo back by ourselves
                            stdout(self.print_write(data))
                        while data != b'' and self.isalive():
                            n = self._write(data)
                            data = data[n:]
                        if i != -1:
                            self.end()
                            break
                    else:
                        self.end()
                        rfdlist.remove(pty.STDIN_FILENO)
                        break
            while True:
                r, w, e = self.__select([self.rfd], [], [], timeout = self.close_delay)
                if self.rfd in r:
                    try:
                        data = None
                        data = os.read(self.rfd, 1024)
                    except OSError, e:
                        if e.errno != errno.EIO:
                            raise
                    # in BSD, you can still read '' from rfd, so never use `data is not None` here
                    if data:
                        if output_filter: data = output_filter(data)
                        stdout(self.print_read(data))
                    else:
                        break
                else:
                    break
        finally:
            if os.isatty(pty.STDIN_FILENO):
                tty.tcsetattr(pty.STDIN_FILENO, tty.TCSAFLUSH, mode)
            if os.isatty(self.wfd):
                self.ttyraw(self.wfd)

    def flush(self):
        """
        just keep to be a file-like object
        """
        pass

    def isatty(self):
        '''This returns True if the file descriptor is open and connected to a
        tty(-like) device, else False. '''

        return os.isatty(self.rfd)

    def ttyraw(self, fd, when = tty.TCSAFLUSH, echo = False):
        mode = tty.tcgetattr(fd)[:]
        mode[tty.IFLAG] = mode[tty.IFLAG] & ~(tty.BRKINT | tty.ICRNL | tty.INPCK | tty.ISTRIP | tty.IXON)
        mode[tty.CFLAG] = mode[tty.CFLAG] & ~(tty.CSIZE | tty.PARENB)
        mode[tty.CFLAG] = mode[tty.CFLAG] | tty.CS8
        if echo:
            mode[tty.LFLAG] = mode[tty.LFLAG] & ~(tty.ICANON | tty.IEXTEN | tty.ISIG)
        else:
            mode[tty.LFLAG] = mode[tty.LFLAG] & ~(tty.ECHO | tty.ICANON | tty.IEXTEN | tty.ISIG)
        mode[tty.CC][tty.VMIN] = 1
        mode[tty.CC][tty.VTIME] = 0
        tty.tcsetattr(fd, when, mode)

    def mode(self):
        
        if not hasattr(self, '_io_mode'):
            
            if hostport_tuple(self.target):
                self._io_mode = SOCKET
            else:
                # TODO: add more check condition
                self._io_mode = PROCESS

        return self._io_mode

    def __select(self, iwtd, owtd, ewtd, timeout=None):

        '''This is a wrapper around select.select() that ignores signals. If
        select.select raises a select.error exception and errno is an EINTR
        error then it is ignored. Mainly this is used to ignore sigwinch
        (terminal resize). '''

        # if select() is interrupted by a signal (errno==EINTR) then
        # we loop back and enter the select() again.
        if timeout is not None:
            end_time = time.time() + timeout
        while True:
            try:
                return select.select(iwtd, owtd, ewtd, timeout)
            except select.error:
                err = sys.exc_info()[1]
                if err[0] == errno.EINTR:
                    # if we loop back we have to subtract the
                    # amount of time we already waited.
                    if timeout is not None:
                        timeout = end_time - time.time()
                        if timeout < 0:
                            return([], [], [])
                else:
                    # something else caused the select.error, so
                    # this actually is an exception.
                    raise

    def writelines(self, sequence):
        n = 0
        for s in sequence:
            n += self.writeline(s)
        return n

    def writeline(self, s = ''):
        return self.write(s + os.linesep)

    def write(self, s):
        if not s: return 0
        if self.mode() == SOCKET:
            if self.print_write: stdout(self.print_write(s))
            self.sock.sendall(s)
            return len(s)
        elif self.mode() == PROCESS:
            #if not self.writable(): raise Exception('subprocess stdin not writable')
            time.sleep(self.write_delay)

            if not isinstance(s, bytes): s = s.encode('utf-8')

            ret = os.write(self.wfd, s)

            # don't use echo backed chars, because
            # 1. input/output will not be cleaner, I mean, they are always in a mess
            # 2. this is a unified interface for pipe/tty write
            # 3. echo back characters will translate control chars into ^@ ^A ^B ^C, ah, ugly!
            if self.print_write: stdout(self.print_write(s))

            return ret

    def end(self, force_close = False):
        '''
        end of writing stream, but we can still read
        '''
        if self.mode() == SOCKET:
            self.sock.shutdown(socket.SHUT_WR)
        else:
            if not os.isatty(self.wfd):     # pipes can be closed harmlessly
                os.close(self.wfd)
            # for pty, close master fd in Mac won't cause slave fd input/output error, so let's do it!
            elif platform.system() == 'Darwin':
                os.close(self.wfd)
            else:       # assume Linux here
                # according to http://linux.die.net/man/3/cfmakeraw
                # set min = 0 and time > 0, will cause read timeout and return 0 to indicate EOF
                # but the tricky thing here is, if child read is invoked before this
                # it will still block forever, so you have to call end before that happens
                mode = tty.tcgetattr(self.wfd)[:]
                mode[tty.CC][tty.VMIN] = 0
                mode[tty.CC][tty.VTIME] = 1
                tty.tcsetattr(self.wfd, tty.TCSAFLUSH, mode)
                if force_close:
                    time.sleep(self.close_delay)
                    os.close(self.wfd)  # might cause EIO (input/output error)! use force_close at your own risk
        return

    def close(self, force = True):
        '''
        close and clean up, nothing can and should be done after closing
        '''
        if self.closed:
            return
        if self.mode() == 'socket':
            if self.sock:
                self.sock.close()
            self.sock = None
        else:
            try:
                os.close(self.wfd)
            except:
                pass    # may already closed in write_eof
            os.close(self.rfd)
            time.sleep(self.close_delay)
            if self.isalive():
                if not self.terminate(force):
                    raise Exception('Could not terminate child process')
        self.flag_eof = True
        self.rfd = -1
        self.wfd = -1
        self.closed = True

    def read(self, size = None):
        if size == 0:
            return str()
        elif size < 0 or size is None:
            self.read_loop(searcher_re(self.compile_pattern_list(EOF)))
            return self.before
        
        cre = re.compile('.{%d}' % size, re.DOTALL)
        index = self.read_loop(searcher_re(self.compile_pattern_list([cre, EOF])))
        if index == 0:
            assert self.before == ''
            return self.after
        return self.before

    def readable(self):
        return self.__select([self.rfd], [], [], 0) == ([self.rfd], [], [])

    def readline(self, size = -1):
        if size == 0:
            return str()
        if self.mode() == PROCESS:
            lineseps = [b'\r\n', EOF]
        else:
            lineseps = [b'\r\n', b'\n', EOF]
        index = self.read_loop(searcher_re(self.compile_pattern_list(lineseps)))
        if index == 0:
            return self.before + b'\n'
        else:
            return self.before

    read_line = readline

    def readlines(self, sizehint = -1):
        lines = []
        while True:
            line = self.readline()
            if not line:
                break
            lines.append(line)
        return lines

    def read_until(self, pattern_list, timeout = -1, searchwindowsize = None):
        if (isinstance(pattern_list, basestring) or
                pattern_list in (TIMEOUT, EOF)):
            pattern_list = [pattern_list]

        def prepare_pattern(pattern):
            if pattern in (TIMEOUT, EOF):
                return pattern
            if isinstance(pattern, basestring):
                return pattern
            self._pattern_type_err(pattern)

        try:
            pattern_list = iter(pattern_list)
        except TypeError:
            self._pattern_type_err(pattern_list)
        pattern_list = [prepare_pattern(p) for p in pattern_list]
        return self.read_loop(searcher_string(pattern_list),
                timeout, searchwindowsize)


    def read_loop(self, searcher, timeout=-1, searchwindowsize = None):

        '''This is the common loop used inside expect. The 'searcher' should be
        an instance of searcher_re or searcher_string, which describes how and
        what to search for in the input.

        See expect() for other arguments, return value and exceptions. '''

        self.searcher = searcher

        if timeout == -1:
            timeout = self.timeout
        if timeout is not None:
            end_time = time.time() + timeout

        try:
            incoming = self.buffer
            freshlen = len(incoming)
            while True:
                # Keep reading until exception or return.
                index = searcher.search(incoming, freshlen, searchwindowsize)
                if index >= 0:
                    self.buffer = incoming[searcher.end:]
                    self.before = incoming[: searcher.start]
                    self.after = incoming[searcher.start: searcher.end]
                    self.match = searcher.match
                    self.match_index = index
                    return self.match_index
                # No match at this point
                if (timeout is not None) and (timeout < 0):
                    raise TIMEOUT('Timeout exceeded in expect_any().')
                # Still have time left, so read more data
                c = self.read_nonblocking(2048, timeout)
                freshlen = len(c)
                time.sleep(0.0001)
                incoming = incoming + c
                if timeout is not None:
                    timeout = end_time - time.time()
        except EOF:
            err = sys.exc_info()[1]
            self.buffer = str()
            self.before = incoming
            self.after = EOF
            index = searcher.eof_index
            if index >= 0:
                self.match = EOF
                self.match_index = index
                return self.match_index
            else:
                self.match = None
                self.match_index = None
                raise EOF(str(err) + '\n' + str(self))
        except TIMEOUT:
            err = sys.exc_info()[1]
            self.buffer = incoming
            self.before = incoming
            self.after = TIMEOUT
            index = searcher.timeout_index
            if index >= 0:
                self.match = TIMEOUT
                self.match_index = index
                return self.match_index
            else:
                self.match = None
                self.match_index = None
                raise TIMEOUT(str(err) + '\n' + str(self))
        except:
            self.before = incoming
            self.after = None
            self.match = None
            self.match_index = None
            raise

    def _pattern_type_err(self, pattern):
        raise TypeError('got {badtype} ({badobj!r}) as pattern, must be one'
                        ' of: {goodtypes}, pexpect.EOF, pexpect.TIMEOUT'\
                        .format(badtype=type(pattern),
                                badobj=pattern,
                                goodtypes=', '.join([str(ast)\
                                    for ast in basestring])
                                )
                        )

    def compile_pattern_list(self, patterns):

        '''This compiles a pattern-string or a list of pattern-strings.
        Patterns must be a StringType, EOF, TIMEOUT, SRE_Pattern, or a list of
        those. Patterns may also be None which results in an empty list (you
        might do this if waiting for an EOF or TIMEOUT condition without
        expecting any pattern).

        This is used by expect() when calling expect_list(). Thus expect() is
        nothing more than::

             cpl = self.compile_pattern_list(pl)
             return self.expect_list(cpl, timeout)

        If you are using expect() within a loop it may be more
        efficient to compile the patterns first and then call expect_list().
        This avoid calls in a loop to compile_pattern_list()::

             cpl = self.compile_pattern_list(my_pattern)
             while some_condition:
                ...
                i = self.expect_list(clp, timeout)
                ...
        '''

        if patterns is None:
            return []
        if not isinstance(patterns, list):
            patterns = [patterns]

        # Allow dot to match \n
        compile_flags = re.DOTALL
        if self.ignorecase:
            compile_flags = compile_flags | re.IGNORECASE
        compiled_pattern_list = []
        for idx, p in enumerate(patterns):
            if isinstance(p, basestring):
                compiled_pattern_list.append(re.compile(p, compile_flags))
            elif p is EOF:
                compiled_pattern_list.append(EOF)
            elif p is TIMEOUT:
                compiled_pattern_list.append(TIMEOUT)
            elif isinstance(p, type(re.compile(''))):
                compiled_pattern_list.append(p)
            else:
                self._pattern_type_err(p)
        return compiled_pattern_list

    def _read(self, size):
        if self.mode() == PROCESS:
            return os.read(self.rfd, size)
        else:
            try:
                return self.sock.recv(size)
            except socket.error, err:
                if err.args[0] == errno.ECONNRESET:
                    raise EOF('Connection reset by peer')
                raise err

    def _write(self, s):
        if self.mode() == PROCESS:
            return os.write(self.wfd, s)
        else:
            self.sock.sendall(s)
            return len(s)

    def read_nonblocking(self, size=1, timeout=-1):
        '''This reads at most size characters from the child application. It
        includes a timeout. If the read does not complete within the timeout
        period then a TIMEOUT exception is raised. If the end of file is read
        then an EOF exception will be raised. 

        If timeout is None then the read may block indefinitely.
        If timeout is -1 then the self.timeout value is used. If timeout is 0
        then the child is polled and if there is no data immediately ready
        then this will raise a TIMEOUT exception.

        The timeout refers only to the amount of time to read at least one
        character. This is not effected by the 'size' parameter, so if you call
        read_nonblocking(size=100, timeout=30) and only one character is
        available right away then one character will be returned immediately.
        It will not wait for 30 seconds for another 99 characters to come in.

        This is a wrapper around os.read(). It uses select.select() to
        implement the timeout. '''

        if self.closed:
            raise ValueError('I/O operation on closed file.')

        if timeout == -1:
            timeout = self.timeout

        # Note that some systems such as Solaris do not give an EOF when
        # the child dies. In fact, you can still try to read
        # from the child_fd -- it will block forever or until TIMEOUT.
        # For this case, I test isalive() before doing any reading.
        # If isalive() is false, then I pretend that this is the same as EOF.
        if not self.isalive():
            # timeout of 0 means "poll"
            r, w, e = self.__select([self.rfd], [], [], 0)
            if not r:
                self.flag_eof = True
                raise EOF('End Of File (EOF). Braindead platform.')

        if timeout is not None and timeout > 0:
            end_time = time.time() + timeout
        else:
            end_time = float('inf')

        readfds = [self.rfd]

        if self.mode() == PROCESS:
            try:
                os.fstat(self.wfd)
                readfds.append(self.wfd)
            except:
                pass

        while True:
            now = time.time()
            if now > end_time: break
            if timeout is not None and timeout > 0:
                timeout = end_time - now
            r, w, e = self.__select(readfds, [], [], timeout)

            if not r:
                if not self.isalive():
                    # Some platforms, such as Irix, will claim that their
                    # processes are alive; timeout on the select; and
                    # then finally admit that they are not alive.
                    self.flag_eof = True
                    raise EOF('End of File (EOF). Very slow platform.')
                else:
                    continue

            if self.mode() == PROCESS:
                try:
                    if self.wfd in r:
                        data = os.read(self.wfd, 1024)
                        if self.print_read and data: stdout(self.print_read(data))
                except OSError, err:
                    # wfd read EOF (echo back)
                    pass

            if self.rfd in r:
                try:
                    s = self._read(size)
                    if self.print_read and s: stdout(self.print_read(s))
                except OSError:
                    # Linux does this
                    self.flag_eof = True
                    raise EOF('End Of File (EOF). Exception style platform.')
                if s == b'':
                    # BSD style
                    self.flag_eof = True
                    raise EOF('End Of File (EOF). Empty string style platform.')

                return s

        raise TIMEOUT('Timeout exceeded. size to read: %d' % size)
        # raise Exception('Reached an unexpected state, timeout = %d' % (timeout))

    def _not_impl(self):
        raise NotImplementedError("Not Implemented")

    # apis below
    read_after = read_before = read_between = read_range = _not_impl

class searcher_string(object):

    '''This is a plain string search helper for the spawn.expect_any() method.
    This helper class is for speed. For more powerful regex patterns
    see the helper class, searcher_re.

    Attributes:

        eof_index     - index of EOF, or -1
        timeout_index - index of TIMEOUT, or -1

    After a successful match by the search() method the following attributes
    are available:

        start - index into the buffer, first byte of match
        end   - index into the buffer, first byte after match
        match - the matching string itself

    '''

    def __init__(self, strings):

        '''This creates an instance of searcher_string. This argument 'strings'
        may be a list; a sequence of strings; or the EOF or TIMEOUT types. '''

        self.eof_index = -1
        self.timeout_index = -1
        self._strings = []
        for n, s in enumerate(strings):
            if s is EOF:
                self.eof_index = n
                continue
            if s is TIMEOUT:
                self.timeout_index = n
                continue
            self._strings.append((n, s))

    def __str__(self):

        '''This returns a human-readable string that represents the state of
        the object.'''

        ss = [(ns[0], '    %d: "%s"' % ns) for ns in self._strings]
        ss.append((-1, 'searcher_string:'))
        if self.eof_index >= 0:
            ss.append((self.eof_index, '    %d: EOF' % self.eof_index))
        if self.timeout_index >= 0:
            ss.append((self.timeout_index,
                '    %d: TIMEOUT' % self.timeout_index))
        ss.sort()
        ss = list(zip(*ss))[1]
        return '\n'.join(ss)

    def search(self, buffer, freshlen, searchwindowsize=None):

        '''This searches 'buffer' for the first occurence of one of the search
        strings.  'freshlen' must indicate the number of bytes at the end of
        'buffer' which have not been searched before. It helps to avoid
        searching the same, possibly big, buffer over and over again.

        See class spawn for the 'searchwindowsize' argument.

        If there is a match this returns the index of that string, and sets
        'start', 'end' and 'match'. Otherwise, this returns -1. '''

        first_match = None

        # 'freshlen' helps a lot here. Further optimizations could
        # possibly include:
        #
        # using something like the Boyer-Moore Fast String Searching
        # Algorithm; pre-compiling the search through a list of
        # strings into something that can scan the input once to
        # search for all N strings; realize that if we search for
        # ['bar', 'baz'] and the input is '...foo' we need not bother
        # rescanning until we've read three more bytes.
        #
        # Sadly, I don't know enough about this interesting topic. /grahn

        for index, s in self._strings:
            if searchwindowsize is None:
                # the match, if any, can only be in the fresh data,
                # or at the very end of the old data
                offset = -(freshlen + len(s))
            else:
                # better obey searchwindowsize
                offset = -searchwindowsize
            n = buffer.find(s, offset)
            if n >= 0 and (first_match is None or n < first_match):
                first_match = n
                best_index, best_match = index, s
        if first_match is None:
            return -1
        self.match = best_match
        self.start = first_match
        self.end = self.start + len(self.match)
        return best_index

class searcher_re(object):

    '''This is regular expression string search helper for the
    spawn.expect_any() method. This helper class is for powerful
    pattern matching. For speed, see the helper class, searcher_string.

    Attributes:

        eof_index     - index of EOF, or -1
        timeout_index - index of TIMEOUT, or -1

    After a successful match by the search() method the following attributes
    are available:

        start - index into the buffer, first byte of match
        end   - index into the buffer, first byte after match
        match - the re.match object returned by a succesful re.search

    '''

    def __init__(self, patterns):

        '''This creates an instance that searches for 'patterns' Where
        'patterns' may be a list or other sequence of compiled regular
        expressions, or the EOF or TIMEOUT types.'''

        self.eof_index = -1
        self.timeout_index = -1
        self._searches = []
        for n, s in zip(list(range(len(patterns))), patterns):
            if s is EOF:
                self.eof_index = n
                continue
            if s is TIMEOUT:
                self.timeout_index = n
                continue
            self._searches.append((n, s))

    def __str__(self):

        '''This returns a human-readable string that represents the state of
        the object.'''

        #ss = [(n, '    %d: re.compile("%s")' %
        #    (n, repr(s.pattern))) for n, s in self._searches]
        ss = list()
        for n, s in self._searches:
            try:
                ss.append((n, '    %d: re.compile("%s")' % (n, s.pattern)))
            except UnicodeEncodeError:
                # for test cases that display __str__ of searches, dont throw
                # another exception just because stdout is ascii-only, using
                # repr()
                ss.append((n, '    %d: re.compile(%r)' % (n, s.pattern)))
        ss.append((-1, 'searcher_re:'))
        if self.eof_index >= 0:
            ss.append((self.eof_index, '    %d: EOF' % self.eof_index))
        if self.timeout_index >= 0:
            ss.append((self.timeout_index, '    %d: TIMEOUT' %
                self.timeout_index))
        ss.sort()
        ss = list(zip(*ss))[1]
        return '\n'.join(ss)

    def search(self, buffer, freshlen, searchwindowsize=None):

        '''This searches 'buffer' for the first occurence of one of the regular
        expressions. 'freshlen' must indicate the number of bytes at the end of
        'buffer' which have not been searched before.

        See class spawn for the 'searchwindowsize' argument.

        If there is a match this returns the index of that string, and sets
        'start', 'end' and 'match'. Otherwise, returns -1.'''

        first_match = None
        # 'freshlen' doesn't help here -- we cannot predict the
        # length of a match, and the re module provides no help.
        if searchwindowsize is None:
            searchstart = 0
        else:
            searchstart = max(0, len(buffer) - searchwindowsize)
        for index, s in self._searches:
            match = s.search(buffer, searchstart)
            if match is None:
                continue
            n = match.start()
            if first_match is None or n < first_match:
                first_match = n
                the_match = match
                best_index = index
        if first_match is None:
            return -1
        self.start = first_match
        self.match = the_match
        self.end = self.match.end()
        return best_index


def which(filename):

    '''This takes a given filename; tries to find it in the environment path;
    then checks if it is executable. This returns the full path to the filename
    if found and executable. Otherwise this returns None.'''

    # Special case where filename contains an explicit path.
    if os.path.dirname(filename) != '':
        if os.access(filename, os.X_OK):
            return filename
    if 'PATH' not in os.environ or os.environ['PATH'] == '':
        p = os.defpath
    else:
        p = os.environ['PATH']
    pathlist = p.split(os.pathsep)
    for path in pathlist:
        ff = os.path.join(path, filename)
        if os.access(ff, os.X_OK):
            return ff
    return None

def split_command_line(command_line):       # this piece of code comes from pexcept, thanks very much!

    '''This splits a command line into a list of arguments. It splits arguments
    on spaces, but handles embedded quotes, doublequotes, and escaped
    characters. It's impossible to do this with a regular expression, so I
    wrote a little state machine to parse the command line. '''

    arg_list = []
    arg = ''

    # Constants to name the states we can be in.
    state_basic = 0
    state_esc = 1
    state_singlequote = 2
    state_doublequote = 3
    # The state when consuming whitespace between commands.
    state_whitespace = 4
    state = state_basic

    for c in command_line:
        if state == state_basic or state == state_whitespace:
            if c == '\\':
                # Escape the next character
                state = state_esc
            elif c == r"'":
                # Handle single quote
                state = state_singlequote
            elif c == r'"':
                # Handle double quote
                state = state_doublequote
            elif c.isspace():
                # Add arg to arg_list if we aren't in the middle of whitespace.
                if state == state_whitespace:
                    # Do nothing.
                    None
                else:
                    arg_list.append(arg)
                    arg = ''
                    state = state_whitespace
            else:
                arg = arg + c
                state = state_basic
        elif state == state_esc:
            arg = arg + c
            state = state_basic
        elif state == state_singlequote:
            if c == r"'":
                state = state_basic
            else:
                arg = arg + c
        elif state == state_doublequote:
            if c == r'"':
                state = state_basic
            else:
                arg = arg + c

    if arg != '':
        arg_list.append(arg)
    return arg_list

def hostport_tuple(target):
    def _check_host(host):
        try:
            socket.gethostbyname(host)
            return True
        except:
            return False
    
    return type(target) == tuple and len(target) == 2 and isinstance(target[1], (int, long)) and target[1] >= 0 and target[1] < 65536 and _check_host(target[0])

def usage():
    print """
usage:

    $ zio.py -h
        you are reading this help message

    $ zio.py [-t seconds] [-i [tty|pipe]] [-o [tty|pipe]] "cmdline -x opts and args"
        spawning process and interact with it

    $ zio.py [-t seconds] host port
        zio becomes a netcat

examples:

    $ ./zio.py tty
    $ ./zio.py cat
    $ ./zio.py vim
    $ ./zio.py ssh -p 22 root@127.0.0.1
    $ ./zio.py xxd
    $ ./zio.py 127.1 22                 # WOW! you can talk with sshd by hand!
    $ ./zio.py -i pipe ssh root@127.1   # you must be crazy to do this!
"""

def cmdline():
    import getopt
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hi:o:t:r:w:d:', ['help', 'stdin', 'stdout', 'timeout', 'read', 'write', 'decode'])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(10)
    
    kwargs = { 
        'stdin': 'tty'
    }
    decode = None
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif o in ('-i', '--stdin'):
            if a.lower() == TTY.lower():
                kwargs['stdin'] = TTY
            else:
                kwargs['stdin'] = PIPE
        elif o in ('-o', '--stdout'):
            if a.lower() == PIPE.lower():
                kwargs['stdout'] = PIPE
            else:
                kwargs['stdout'] = TTY
        elif o in ('-t', '--timeout'):
            try:
                kwargs['timeout'] = int(a)
            except:
                usage()
                sys.exit(11)
        elif o in ('-r', '--read'):
            if a.lower() == 'hex':
                kwargs['print_read'] = COLORED(HEX, 'yellow')
            elif a.lower() == 'repr':
                kwargs['print_read'] = COLORED(REPR, 'yellow')
            elif a.lower() == 'none':
                kwargs['print_read'] = NONE
            else:
                kwargs['print_read'] = RAW
        elif o in ('-w', '--write'):
            if a.lower() == 'hex':
                kwargs['print_write'] = COLORED(HEX, 'cyan')
            elif a.lower() == 'repr':
                kwargs['print_write'] = COLORED(REPR, 'cyan')
            elif a.lower() == 'none':
                kwargs['print_write'] = NONE
            else:
                kwargs['print_write'] = RAW
        elif o in ('-d', '--decode'):
            if a.lower() == 'eval':
                decode = EVAL
            elif a.lower() == 'unhex':
                decode = UNHEX

    target = None
    if len(args) == 2:
        try:
            port = int(args[1])
            if hostport_tuple((args[0], port)):
                target = (args[0], port)
        except:
            pass
    if not target:
        if len(args) == 1:
            target = args[0]
        else:
            target = args

    io = zio(target, **kwargs)
    io.interact(input_filter = decode)

if __name__ == '__main__':

    if len(sys.argv) >= 2:
        test = sys.argv[1]
    else:
        usage()
        sys.exit(0)

    cmdline()

# vi:set et ts=4 sw=4 ft=python :
