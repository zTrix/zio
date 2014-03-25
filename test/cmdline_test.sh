#!/bin/bash

printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe  xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -r none xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -r hex xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -r repr xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -w none xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -w hex xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -w repr xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -r hex -w hex xxd
echo '"\x01\x02\x05"' | ./zio.py -d eval -w none -r raw -i pipe xxd
echo '03051893' | ./zio.py -d unhex -w none -r raw -i pipe xxd
