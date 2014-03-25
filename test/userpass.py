
import getpass
import sys

print 'Welcome'

user = raw_input('Username: ')

# note the stream param, if leave blank, zio won't read password prompt, because it's echoed back
# from tty stdin, while zio handle stdin and stdout/stderr in two ttys.
pswd = getpass.getpass('Password: ', stream = sys.stdout)

if user == 'user' and pswd == 'pass':
    print 'Logged in'
else:
    print 'Invalid', repr(user), repr(pswd)

