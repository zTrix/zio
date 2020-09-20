#!/bin/sh

set -ex

cd "${0%/*}" && pwd

PYTHON=`which python3 || which python`

$PYTHON ./test_basic.py
