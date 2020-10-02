#!/usr/bin/env python

import os, sys
from zio import EVAL as evals
from zio import write_stdout

write_stdout(evals(sys.argv[1].encode()))
