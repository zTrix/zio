#!/bin/sh

set -ex

cd "${0%/*}" && pwd

PYTHON=`which python2 || which python`

$PYTHON ./test_basic.py
