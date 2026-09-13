#!/bin/sh
set -u
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root" || exit 1
failed=0
leg() {
  name=$1; shift
  if "$@"; then printf 'PASS %s\n' "$name"
  else printf 'FAIL %s\n' "$name"; failed=1
  fi
}
leg M1-HASHES sh dev/m1-hashes.sh
leg SETS-BUILD dune build bin/tether.exe dev/store_run.exe dev/sets_tests.exe
leg SETS-UNIT _build/default/dev/sets_tests.exe
leg SETS-TESTS python3 -P dev/sets-tests.py
leg SETS-MUTATIONS python3 -P dev/sets-mutations.py
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-SETS'; exit 1; fi
printf '%s\n' 'PASS M1-SETS'
