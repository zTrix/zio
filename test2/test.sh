#!/bin/sh

set -ex

cd "${0%/*}" && pwd

PYTHON=`which python2 || which python`

PYVER=`$PYTHON -V 2>&1`

case $PYVER in

"Python 2"*)
    $PYTHON ./test_basic.py
    ;;

*)
    echo "found PYVER=$PYVER, not Python2, skip test"
    ;;
esac

