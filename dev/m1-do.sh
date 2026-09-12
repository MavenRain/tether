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
leg STAGE-F sh dev/stage-f.sh
leg DO-BUILD dune build dev/do_tests.exe
leg DO-SYNTAX _build/default/dev/do_tests.exe
leg DO-TESTS python3 -P dev/do-tests.py
leg DO-MUTATIONS python3 -P dev/do-mutations.py
leg HOUSE sh dev/house.sh
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-DO'; exit 1; fi
printf '%s\n' 'PASS M1-DO'
