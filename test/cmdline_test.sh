#!/bin/bash

printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe  xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -r none xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -r hex xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -r repr xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -w none xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -w hex xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -w repr xxd
printf '\x01\x02\x03asdfasasdf\n' | ./zio.py -i pipe -r hex -w hex xxd
