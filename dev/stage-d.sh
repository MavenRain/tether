#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
sh dev/stage-c.sh
dune build dev/sh_emit.exe
python3 -P dev/stage-d-tests.py
printf '%s\n' 'PASS STAGE-D'
