#!/bin/bash

set -ex

CWD=$(cd "${0%/*}" && pwd)

docker=podman

$docker run -it --rm -v $CWD:/data/ python:2.6 /data/test2/test.sh
$docker run -it --rm -v $CWD:/data/ python:2.7 /data/test2/test.sh
$docker run -it --rm -v $CWD:/data/ python:3.5 /data/test3/test.sh
$docker run -it --rm -v $CWD:/data/ python:3.7 /data/test3/test.sh
