#!/bin/bash

set -ex

cd "${0%/*}" && pwd

PYTHON=`which python2`

$PYTHON ./test_packing.py
