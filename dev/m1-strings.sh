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
leg M1-READONLY sh dev/m1-readonly.sh
leg STRINGS-BUILD dune build bin/tether.exe dev/store_run.exe dev/strings_tests.exe
leg STRINGS-UNIT _build/default/dev/strings_tests.exe
leg STRINGS-TESTS python3 -P dev/strings-tests.py
leg STRINGS-MUTATIONS python3 -P dev/strings-mutations.py
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-STRINGS'; exit 1; fi
printf '%s\n' 'PASS M1-STRINGS'
