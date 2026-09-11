#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
sh dev/stage-d.sh
dune build dev/store_run.exe dev/store_tests.exe
_build/default/dev/store_tests.exe
node --test dev/host-tests.mjs
python3 -P dev/stage-e-tests.py
python3 -P dev/trusted-lines.py
printf '%s\n' 'PASS STAGE-E'
