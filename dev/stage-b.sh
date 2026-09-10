#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
sh dev/stage-a.sh
dune build dev/surface_check.exe
sh dev/house.sh
python3 -P dev/stage-b-tests.py
python3 -P dev/trusted-lines.py
python3 -P dev/stage-b-mutations.py
printf '%s\n' 'PASS STAGE-B'
