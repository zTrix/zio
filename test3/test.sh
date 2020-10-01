#!/bin/sh

set -ex

cd "${0%/*}" && pwd

PYTHON=`which python3 || which python`

PYVER=`$PYTHON -V 2>&1`

case $PYVER in

"Python 3"*)
    $PYTHON ./test_basic.py
    ;;

*)
    echo "found PYVER=$PYVER, not Python3, skip test"
    ;;
esac

