#!/usr/bin/env python2

import struct, socket, os, sys, subprocess, threading, pty, time, re, select, termios, resource, tty, errno, signal, fcntl, gc
from StringIO import StringIO
try:
    from termcolor import colored
except:
    def colored(text, color=None, on_color=None, attrs=None):
        return text

__ALL__ = ['stdout', 'log', 'l16', 'b16', 'l32', 'b32', 'l64', 'b64', 'zio', 'EOF', 'TIMEOUT']

def stdout(s, color = None, on_color = None, attrs = None):
    if not color:
        sys.stdout.write(s)
    else:
        sys.stdout.write(colorde(s, color, on_color, attrs))
    sys.stdout.flush()

def log(s, color = None, on_color = None, attrs = None, new_line = True):
    if not color:
        print >> sys.stderr, str(s),
    else:
        print >> sys.stderr, colored(str(s), color, on_color, attrs),
    if new_line:
        sys.stderr.write('\n')
    sys.stderr.flush()

def l16(i):
    return struct.pack('<H', i)

def b16(i):
    return struct.pack('>H', i)

def l32(i):
    return struct.pack('<I', i)

def b32(i):
    return struct.pack('>I', i)

def l64(i):
    return struct.pack('<Q', i)

def b64(i):
    return struct.pack('>Q', i)

class EOF(Exception):
    """Raised when EOF is read from child or socket.
    This usually means the child has exited or socket closed"""

class TIMEOUT(Exception):
    """Raised when a read timeout exceeds the timeout. """

class zio(object):

    IO_SOCKET = 'socket'
    IO_PROCESS = 'process'

    # TODO: logfile support ?
    def __init__(self, target, print_read = True, print_write = True, print_log = True, timeout = 10, cwd = None, env = None, ignore_sighup = True, write_delay = 0.05, ignorecase = False):
        """
        zio is an easy-to-use io library for your target, currently zio supports process io and tcp socket

        example:

        io = zio(('localhost', 80))
        io = zio('ls -l')
        io = zio(['ls', '-l'])

        params:
            print_read = bool, if true, print all the data read from target
            print_write = bool, if true, print all the data sent out
            print_log = bool, if true, print the zio log file
        """

        if not target:
            raise Exception('cmdline or socket not provided for zio, try zio("ls -l")')

        self.target = target
        self.print_read = print_read
        self.print_write = print_write
        self.print_log = print_log

        if isinstance(timeout, (int, long)) and timeout > 0:
            self.timeout = timeout
        else:
            self.timeout = 10
        self.write_fd = -1          # the fd to write to, no matter subprocess or socket
        self.read_fd = -1           # the fd to read from, no matter subprocess or socket
        self.exit_status = None     # subprocess exit status, for socket, should be 0 if closed normally, or others if exception occurred
        
        self.write_delay = write_delay     # the delay before writing data, pexcept said Linux don't like this to be below 30ms
        self.close_delay = 0.1      # like pexcept, will used by close(), to give kernel time to update process status, time in seconds
        self.terminate_delay = 0.1  # like close_delay
        self.cwd = cwd
        self.env = env
        self.ignore_sighup = ignore_sighup
     
        self.flag_eof = False
        self.closed = True
        self.terminated = True

        self.ignorecase = ignorecase

        self.buffer = str()

        if self.io_type() == 'socket':
            #TODO: udp support ?
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(self.target)
            self.name = '<socket ' + self.target[0] + ':' + str(self.target[1]) + '>'
        else:
            self.pid = None
            self._spawn(target)

    def _spawn(self, target):
        
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

        master_fd, slave_fd = pty.openpty()
        if master_fd < 0 or slave_fd < 0:
            raise Exception('Could not openpty for stdout/stderr')

        # use another pty for stdin because we don't want our input to be echoed back in stdout
        # set echo off does not help because in application like ssh, when you input the password
        # echo will be switched on again
        # and dont use os.pipe either, because many thing weired will happen, such as baskspace not working, ssh lftp command hang

        p2cwrite, p2cread = pty.openpty() # p2cread, p2cwrite = self.pipe_cloexec()
        if p2cwrite < 0 or p2cread < 0:
            raise Exception('Could not openpty for stdin')

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
        elif self.pid == 0:
            # Child
            os.close(master_fd)

            self.__pty_make_controlling_tty(p2cread)
            # self.__pty_make_controlling_tty(slave_fd)

            try:
                # self.setwinsize(sys.stdout.fileno(), 24, 80)     # note that this may not be successful
                pass
            except BaseException, ex:
                if self.print_log: log('[ WARN ] setwinsize exception: %s' % (str(ex)), 'yellow')
                pass

            # redirect stdout and stderr to pty
            # but don't redirect stdin, because it will get echoed back, which is not what we want

            os.dup2(slave_fd, pty.STDOUT_FILENO)
            os.dup2(slave_fd, pty.STDERR_FILENO)

            if slave_fd > 2:
                os.close(slave_fd)

            if p2cwrite is not None:
                os.close(p2cwrite)

            # Dup fds for child
            def _dup2(a, b):
                # dup2() removes the CLOEXEC flag but
                # we must do it ourselves if dup2()
                # would be a no-op (issue #10806).
                if a == b:
                    self._set_cloexec_flag(a, False)
                elif a is not None:
                    os.dup2(a, b)
            _dup2(p2cread, pty.STDIN_FILENO)

            # do not allow child to inherit open file descriptors from parent

            max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
            os.closerange(3, max_fd)

            if self.ignore_sighup:
                signal.signal(signal.SIGHUP, signal.SIG_IGN)

            if self.cwd is not None:
                os.chdir(self.cwd)

            if self.env is None:
                os.execv(self.command, self.args)
            else:
                os.execvpe(self.command, self.args, self.env)
            
            # TODO: add subprocess errpipe to detech child error
            # child exit here, the same as subprocess module do
            os._exit(255)

        else:
            # after fork, parent
            self.write_fd = p2cwrite
            os.close(p2cread)
            self.read_fd = master_fd
            os.close(slave_fd)
            if gc_enabled:
                gc.enable()

        # parent goes here
        self.terminated = False
        self.closed = False

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
        return r, w

    def fileno(self):
        '''This returns the file descriptor of the pty for the child.
        '''
        return self.read_fd

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

    def getwinsize(self):

        '''This returns the terminal window size of the child tty. The return
        value is a tuple of (rows, cols). '''

        TIOCGWINSZ = getattr(termios, 'TIOCGWINSZ', 1074295912)
        s = struct.pack('HHHH', 0, 0, 0, 0)
        x = fcntl.ioctl(self.fileno(), TIOCGWINSZ, s)
        return struct.unpack('HHHH', x)[0:2]

    def __str__(self):
        ret = ['io-type: %s' % self.io_type(), 
               'name: %s' % self.name, 
               'timeout: %f' % self.timeout,
               'write-fd: %d' % self.write_fd,
               'read-fd: %d' % self.read_fd,
               'buffer(last 100 chars): %r' % (self.buffer[-100:])]
        if self.io_type() == zio.IO_SOCKET:
            pass
        elif self.io_type() == zio.IO_PROCESS:
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
            self.kill(signal.SIGINT)
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
        self.exitstatus = os.WEXITSTATUS(status)
        if os.WIFEXITED(status):
            self.status = status
            self.exitstatus = os.WEXITSTATUS(status)
            self.signalstatus = None
            self.terminated = True
        elif os.WIFSIGNALED(status):
            self.status = status
            self.exitstatus = None
            self.signalstatus = os.WTERMSIG(status)
            self.terminated = True
        elif os.WIFSTOPPED(status):
            # You can't call wait() on a child process in the stopped state.
            raise Exception('Called wait() on a stopped child ' +
                    'process. This is not supported. Is some other ' +
                    'process attempting job control with our child pid?')
        return self.exitstatus

    def isalive(self):

        '''This tests if the child process is running or not. This is
        non-blocking. If the child was terminated then this will read the
        exitstatus or signalstatus of the child. This returns True if the child
        process appears to be running or False if not. It can take literally
        SECONDS for Solaris to return the right status. '''

        if self.terminated:
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
            self.status = status
            self.exitstatus = os.WEXITSTATUS(status)
            self.signalstatus = None
            self.terminated = True
        elif os.WIFSIGNALED(status):
            self.status = status
            self.exitstatus = None
            self.signalstatus = os.WTERMSIG(status)
            self.terminated = True
        elif os.WIFSTOPPED(status):
            raise Exception('isalive() encountered condition ' +
                    'where child process is stopped. This is not ' +
                    'supported. Is some other process attempting ' +
                    'job control with our child pid?')
        return False

    def interact(self, escape_character=chr(29), input_filter = None, output_filter = None):
        """
        when stdin is passed using os.pipe, backspace key will not work as expected, 
        if write_fd is not a tty, then when backspace pressed, I can see that 0x7f is passed, but vim does not delete backwards, so I choose to translate 0x7f to ^H by default, by setting input_filter = lambda x: x.replace('\x7f', '\x08')
        """
        stdout(self.buffer)
        self.buffer = str()
        mode = tty.tcgetattr(pty.STDIN_FILENO)
        tty.setraw(pty.STDIN_FILENO)
        try:
                
            while self.isalive():
                # write_fd for tty echo
                r, w, e = self.__select([self.read_fd, pty.STDIN_FILENO, self.write_fd], [], [])
                if self.write_fd in r:          # handle tty echo first
                    try:
                        data = None
                        data = os.read(self.write_fd, 1024)
                    except OSError, e:
                        if e.errno != errno.EIO:
                            raise
                    if data is not None:
                        if output_filter: data = output_filter(data)
                        os.write(pty.STDOUT_FILENO, data)
                if self.read_fd in r:
                    try:
                        data = None
                        data = os.read(self.read_fd, 1024)
                    except OSError, e:
                        if e.errno != errno.EIO:
                            raise
                    if data is not None:
                        if output_filter: data = output_filter(data)
                        os.write(pty.STDOUT_FILENO, data)
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
                        while data != b'' and self.isalive():
                            n = os.write(self.write_fd, data)
                            data = data[n:]
                        if i != -1:
                            break
            while True:
                r, w, e = self.__select([self.read_fd], [], [], timeout = self.close_delay)
                if self.read_fd in r:
                    try:
                        data = None
                        data = os.read(self.read_fd, 1024)
                    except OSError, e:
                        if e.errno != errno.EIO:
                            raise
                    if data is not None:
                        if output_filter: data = output_filter(data)
                        os.write(pty.STDOUT_FILENO, data)
                    else:
                        break
                else:
                    break
        finally:
            tty.tcsetattr(pty.STDIN_FILENO, tty.TCSAFLUSH, mode)

    def flush(self):
        """
        just keep to be a file-like object
        """
        pass

    def isatty(self):
        '''This returns True if the file descriptor is open and connected to a
        tty(-like) device, else False. '''

        return os.isatty(self.read_fd)

    def waitnoecho(self, timeout=-1):
        '''This waits until the terminal ECHO flag is set False. This returns
        True if the echo mode is off. This returns False if the ECHO flag was
        not set False before the timeout. This can be used to detect when the
        child is waiting for a password. Usually a child application will turn
        off echo mode when it is waiting for the user to enter a password. For
        example, instead of expecting the "password:" prompt you can wait for
        the child to set ECHO off::

            p = pexpect.spawn('ssh user@example.com')
            p.waitnoecho()
            p.sendline(mypassword)

        If timeout==-1 then this method will use the value in self.timeout.
        If timeout==None then this method to block until ECHO flag is False.
        '''

        if timeout == -1:
            timeout = self.timeout
        if timeout is not None:
            end_time = time.time() + timeout
        while True:
            if not self.getecho():
                return True
            if timeout < 0 and timeout is not None:
                return False
            if timeout is not None:
                timeout = end_time - time.time()
            time.sleep(0.1)

    def getecho(self, fd):
        '''This returns the terminal echo mode. This returns True if echo is
        on or False if echo is off. Child applications that are expecting you
        to enter a password often set ECHO False. See waitnoecho(). '''

        attr = termios.tcgetattr(self.fd)
        if attr[3] & termios.ECHO:
            return True
        return False

    def setecho(self, fd, state):

        attr = termios.tcgetattr(self.read_fd)
        if state:
            attr[3] = attr[3] | termios.ECHO
        else:
            attr[3] = attr[3] & ~termios.ECHO
        # I tried TCSADRAIN and TCSAFLUSH, but
        # these were inconsistent and blocked on some platforms.
        # TCSADRAIN would probably be ideal if it worked.
        termios.tcsetattr(self.fd, termios.TCSANOW, attr)

    def seterase(self, fd, erase_char = chr(0x7f)):
        attr = termios.tcgetattr(fd)
        attr[6][termios.VERASE] = erase_char
        termios.tcsetattr(fd, termios.TCSANOW, attr)

    def io_type(self):
        
        def _check_host(host):
            try:
                socket.gethostbyname(host)
                return True
            except:
                return False
        
        if not hasattr(self, '_io_type'):
            
            if type(self.target) == tuple and len(self.target) == 2 and isinstance(self.target[1], (int, long)) and self.target[1] >= 0 and self.target[1] < 65536 and _check_host(self.target[0]):
                self._io_type = zio.IO_SOCKET
            else:
                # TODO: add more check condition
                self._io_type = zio.IO_PROCESS

        return self._io_type

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

    def _not_impl(self):
        raise NotImplementedError("Not Implemented")

    def writelines(self, sequence):
        n = 0
        for s in sequence:
            n += self.writeline(s)
        return n

    def writeline(self, s = ''):
        n = self.write(s)
        n += self.write(os.linesep)
        return n

    def write(self, s):
        if self.io_type() == zio.IO_SOCKET:
            #self.lock.acquire()
            if self.print_write: stdout(s)
            self.sock.sendall(s)
            #self.lock.release()
            return len(s)
        elif self.io_type() == zio.IO_PROCESS:
            #if not self.writable(): raise Exception('subprocess stdin not writable')
            #self.lock.acquire()
            time.sleep(self.write_delay)

            if not isinstance(s, bytes): s = s.encode('utf-8')

            ret = os.write(self.write_fd, s)

            r, w, e = self.__select([self.write_fd], [], [], self.write_delay + 0.01)

            try:
                if r and self.write_fd in r:
                    data = os.read(self.write_fd, 1024)
                    if self.print_read and data:
                        n = os.write(pty.STDOUT_FILENO, data)
            except OSError, err:
                # write_fd got EOF
                pass

            return ret

            #self.lock.release()

    def writeeof(self):
        if hasattr(termios, 'VEOF'):
            char = ord(termios.tcgetattr(self.write_fd)[6][termios.VEOF])
        else:
            # platform does not define VEOF so assume CTRL-D
            char = 4
        self.write(chr(char))

    write_eof = writeeof

    def writecontrol(self, char):

        '''Helper method that wraps send() with mnemonic access for sending control
        character to the child (such as Ctrl-C or Ctrl-D).  For example, to send
        Ctrl-G (ASCII 7, bell, '\a')::

            child.sendcontrol('g')

        See also, sendintr() and sendeof().
        '''

        char = char.lower()
        a = ord(char)
        if a >= 97 and a <= 122:
            a = a - ord('a') + 1
            return self.write(chr(a))
        d = {'@': 0, '`': 0,
            '[': 27, '{': 27,
            '\\': 28, '|': 28,
            ']': 29, '}': 29,
            '^': 30, '~': 30,
            '_': 31,
            '?': 127}
        if char not in d:
            return 0
        return self.write(chr(d[char]))


    def close(self, force = True):
        if self.io_type() == 'socket':
            self.lock.acquire()
            self.sock.close()
            self.lock.release()
        else:
            if not self.closed:
                self.flush()
                os.close(self.write_fd)
                os.close(self.read_fd)
                time.sleep(self.close_delay)
                if self.isalive():
                    if not self.terminate(force):
                        raise Exception('Could not terminate child process')
                self.read_fd = -1
                self.write_fd = -1
                self.closed = True

    def _read(self, size):
        if self.io_type() == 'socket':
            return self.sock.recv(size)
        else:
            #TODO: filter first \r out
            #TODO: eof detection, pty won't give us eof
            return self.proc.output.read(size)

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

    def readline(self, size = -1):
        if size == 0:
            return str()
        index = self.read_loop(searcher_re(self.compile_pattern_list([b'\r\n', EOF])))
        if index == 0:
            return self.before + b'\n'
        else:
            return self.before

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


    def read_nonblocking(self, size=1, timeout=-1):
        '''This reads at most size characters from the child application. It
        includes a timeout. If the read does not complete within the timeout
        period then a TIMEOUT exception is raised. If the end of file is read
        then an EOF exception will be raised. If a log file was set using
        setlog() then all data will also be written to the log file.

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
            r, w, e = self.__select([self.read_fd], [], [], 0)
            if not r:
                self.flag_eof = True
                raise EOF('End Of File (EOF). Braindead platform.')

        if timeout is not None and timeout > 0:
            end_time = time.time() + timeout
        else:
            end_time = float('inf')

        while time.time() < end_time:
            if timeout is not None and timeout > 0:
                timeout = end_time - time.time()
            r, w, e = self.__select([self.read_fd, self.write_fd], [], [], timeout)

            if not r:
                if not self.isalive():
                    # Some platforms, such as Irix, will claim that their
                    # processes are alive; timeout on the select; and
                    # then finally admit that they are not alive.
                    self.flag_eof = True
                    raise EOF('End of File (EOF). Very slow platform.')
                else:
                    continue

            try:
                if self.write_fd in r:
                    data = os.read(self.write_fd, 1024)
                    if self.print_read and data:
                        n = os.write(pty.STDOUT_FILENO, data)
            except OSError, err:
                # write_fd read EOF (echo back)
                pass

            if self.read_fd in r:
                try:
                    s = os.read(self.read_fd, size)
                    if self.print_read and s: os.write(pty.STDOUT_FILENO, s)
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

    # apis below
    read_after = read_before = read_between = read_range = read_line = readable = _not_impl

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

if __name__ == '__main__':

    test = 'tty'
    if len(sys.argv) >= 2:
        test = sys.argv[1]

    if test == 'tty':
        io = zio('tty')
        io.interact()
    elif test == 'vim':
        io = zio('vim', write_delay = 0)
        io.interact()
    elif test == 'cat':
        io = zio('cat')
        io.write('hello zio')
        io.interact()
    elif test == 'ssh':
        io = zio('ssh root@127.0.0.1')
        io.interact()
    elif test == 'getpass':
        f = open('/tmp/_test_getpass_zio.py', 'w')
        f.write("\nimport getpass\n\nprint 'Welcome'\n\na = getpass.getpass('Password:')\n\nif a == 'pass':\n    print 'Logged in'\nelse:\n    print 'Invalid'\n\n")
        f.close()
        io = zio('python2 /tmp/_test_getpass_zio.py')
        io.interact()

