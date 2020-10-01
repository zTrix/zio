
import getpass
import sys

print 'LOG In'

user = raw_input('Username: ')

# note the stream param, if leave blank, zio won't read password prompt, because it's echoed back
# from tty stdin, while zio handle stdin and stdout/stderr in two ttys.
password = getpass.getpass('Password: ', stream = sys.stdout)

if user == 'user' and password == 'pass':
    print 'Logging in'
else:
    print 'Invalid', repr(user), 'or', repr(password)

