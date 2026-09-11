#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
sh dev/stage-b.sh
dune build dev/lua_emit.exe dev/sha1_probe.exe
python3 -P dev/prelude-check.py
python3 -P dev/stage-c-tests.py
python3 -P dev/stage-c-integrity.py
printf '%s\n' 'PASS STAGE-C'
