#!/bin/bash

set -ex

cd "${0%/*}" && pwd

PYTHON=`which python3`

$PYTHON ./test_packing.py
