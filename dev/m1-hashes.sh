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
leg M1-STRINGS sh dev/m1-strings.sh
leg HASHES-BUILD dune build bin/tether.exe dev/store_run.exe dev/hashes_tests.exe
leg HASHES-UNIT _build/default/dev/hashes_tests.exe
leg HASHES-TESTS python3 -P dev/hashes-tests.py
leg HASHES-MUTATIONS python3 -P dev/hashes-mutations.py
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-HASHES'; exit 1; fi
printf '%s\n' 'PASS M1-HASHES'
