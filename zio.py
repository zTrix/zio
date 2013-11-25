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
    def __init__(self, target, print_read = True, print_write = True, print_log = True, timeout = 30, cwd = None, env = None, ignore_sighup = True):
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

        self.timeout = timeout
        self.write_fd = -1          # the fd to write to, no matter subprocess or socket
        self.exit_status = None     # subprocess exit status, for socket, should be 0 if closed normally, or others if exception occurred
        
        self.write_delay = 0.05     # the delay before writing data, pexcept said Linux don't like this to be below 30ms
        self.close_delay = 0.1      # like pexcept, will used by close(), to give kernel time to update process status, time in seconds
        self.terminate_delay = 0.1  # like close_delay
        self.cwd = cwd
        self.env = env
        self.ignore_sighup = ignore_sighup
     
        self.flag_eof = False
        self.closed = True
        self.terminated = True

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

        try:
            self.pid, self.write_fd = pty.fork()
        except OSError:
            err = sys.exc_info()[1]
            raise Exception('pty.fork() failed: ' + str(err))

        # if self.print_log: log('self.pid = %d, child_fd = %d' % (self.pid, self.write_fd))

        if self.pid == 0:   # Child
            try:
                self.write_fd = sys.stdout.fileno()
                self.setwinsize(24, 80)     # note that this may not be successful
            except BaseException, ex:
                if self.print_log: log('[ WARN ] setwinsize exception: %s' % (str(ex)), 'yellow')
                pass

            # do not allow child to inherit open file descriptors from parent

            max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
            for i in range(3, max_fd):
                try:
                    os.close(i)
                except OSError:     # this error does not matter, we just try out all possible fds
                    pass

            if self.ignore_sighup:
                signal.signal(signal.SIGHUP, signal.SIG_IGN)

            if self.cwd is not None:
                os.chdir(self.cwd)

            # Child will end here

            if self.env is None:
                os.execv(self.command, self.args)
            else:
                os.execvpe(self.command, self.args, self.env)

        # parent goes here
        self.terminated = False
        self.closed = False

    def fileno(self):
        '''This returns the file descriptor of the pty for the child.
        '''
        return self.write_fd

    def setwinsize(self, rows, cols):   # from pexpect, thanks!

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
        fcntl.ioctl(self.fileno(), TIOCSWINSZ, s)

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
               'write-fd: %d' % self.write_fd]
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
            raise ExceptionPexpect('Cannot wait for dead child process.')
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
            raise ExceptionPexpect('Called wait() on a stopped child ' +
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
        mode = tty.tcgetattr(pty.STDIN_FILENO)
        tty.setraw(pty.STDIN_FILENO)
        try:
            while self.isalive():
                r, w, e = self.__select([self.write_fd, pty.STDIN_FILENO], [], [])
                if self.write_fd in r:
                    try:
                        data = os.read(self.write_fd, 1024)
                    except OSError, e:
                        if e.errno != errno.EIO:
                            raise
                    if output_filter: data = output_filter(data)
                    os.write(pty.STDOUT_FILENO, data)
                if pty.STDIN_FILENO in r:
                    data = os.read(pty.STDIN_FILENO, 1024)
                    if input_filter:
                        data = input_filter(data)
                    i = data.rfind(escape_character)
                    if i != -1:
                        data = data[:i]
                    while data != b'' and self.isalive():
                        n = os.write(self.write_fd, data)
                        data = data[n:]
                    if i != -1:
                        break

        finally:
            tty.tcsetattr(pty.STDIN_FILENO, tty.TCSAFLUSH, mode)

    def flush(self):
        """
        just keep to be a file-like object
        """
        pass

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

    def write(self, s):
        if self.io_type() == zio.IO_SOCKET:
            #self.lock.acquire()
            if self.print_write: stdout(s)
            self.sock.sendall(s)
            #self.lock.release()
        elif self.io_type() == zio.IO_PROCESS:
            #if not self.writable(): raise Exception('subprocess stdin not writable')
            #self.lock.acquire()
            time.sleep(self.write_delay)

            if not isinstance(s, bytes): s = s.encode('utf-8')

            if self.print_write: stdout(s)
            os.write(self.write_fd, s)

            #self.lock.release()

    def writeeof(self):
        if hasattr(termios, 'VEOF'):
            char = ord(termios.tcgetattr(self.child_fd)[6][termios.VEOF])
        else:
            # platform does not define VEOF so assume CTRL-D
            char = 4
        self.write(chr(char))

    def close(self):
        if self.io_type() == 'socket':
            self.lock.acquire()
            self.sock.close()
            self.lock.release()

    def _read(self, size):
        if self.io_type() == 'socket':
            return self.sock.recv(size)
        else:
            #TODO: filter first \r out
            #TODO: eof detection, pty won't give us eof
            return self.proc.output.read(size)

    def read(self, size = None):
        if size is None:    # read to end
            size = float('inf')
        rd = 0
        ret = StringIO()
        while rd < size:
            bufsize = size - rd < 4096 and size - rd or 4096
            buf = self._read(bufsize)
            if not buf: break
            if self.print_read: stdout(buf)
            ret.write(buf)
        return ret.getvalue()

    def read_until(self, s):
        # TODO: support regex, function
        
        ret = StringIO()
        while True:
            char = self._read(1)
            if not char: break
            if self.print_read: stdout(char)
            ret.write(buf)
            if ret.getvalue().find(s) > -1: break

        return ret.getvalue()

    # apis below
    writeable = _not_impl
    read = read_until = read_after = read_before = read_between = read_range = readline = read_line = readable = _not_impl
    close = _not_impl

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
    io = zio('cat')
    for i in range(10):
        io.write(str(i) * 10 + '\n')
    #io.read(4)
    io.interact()
