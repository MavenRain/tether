#!/bin/sh
set -u
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root" || exit 1
failed=0
work=$(mktemp -d) || exit 1
trap 'rm -rf "$work"' EXIT HUP INT TERM
leg() {
  name=$1; shift
  if "$@"; then printf 'PASS %s\n' "$name"
  else printf 'FAIL %s\n' "$name"; failed=1
  fi
}
capture() {
  out=$1; shift
  "$@" > "$out" 2>&1
  status=$?
  cat "$out"
  return "$status"
}
row() {
  while IFS= read -r line; do
    if [ "$line" = "$2" ]; then return 0; fi
  done < "$1"
  printf 'MISSING ROW %s\n' "$2"
  return 1
}
counts() {
  missing=0
  row "$work/unit.txt" 'PASS LIST-REMOVE-UNIT cases=135' || missing=1
  row "$work/tests.txt" 'PASS LIST-REMOVE-ARTIFACTS pairs=18' || missing=1
  row "$work/tests.txt" 'PASS LIST-REMOVE-REFUSALS cases=17 atomic_output=17' || missing=1
  row "$work/tests.txt" 'PASS LIST-REMOVE-ORACLES store=41 luajit=41' || missing=1
  row "$work/tests.txt" 'PASS LIST-REMOVE-E2E cases=47 hosts=104 utf8_refusals=2 errors=4 expired=6' || missing=1
  row "$work/tests.txt" 'PASS LIST-REMOVE-EXAMPLE exec=9' || missing=1
  row "$work/tests.txt" 'PASS LIST-REMOVE-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS LIST-REMOVE-MUTATIONS killed=14 survived=0 restored=5' || missing=1
  return "$missing"
}
leg M1-LIST-CONDITIONAL sh dev/m1-list-conditional.sh
if dune build -j 2 bin/tether.exe dev/store_run.exe dev/list_remove_tests.exe; then
  printf '%s\n' 'PASS LIST-REMOVE-BUILD'
  leg LIST-REMOVE-UNIT-EXE capture "$work/unit.txt" _build/default/dev/list_remove_tests.exe
  leg LIST-REMOVE-TESTS-RUN capture "$work/tests.txt" python3 -P dev/list-remove-tests.py
  leg LIST-REMOVE-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/list-remove-mutations.py
  leg LIST-REMOVE-COUNTS counts
else
  printf '%s\n' 'FAIL LIST-REMOVE-BUILD'
  failed=1
  for name in LIST-REMOVE-UNIT-EXE LIST-REMOVE-TESTS-RUN LIST-REMOVE-MUTATIONS-RUN LIST-REMOVE-COUNTS; do
    printf 'SKIPPED %s after a red LIST-REMOVE-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg PRELUDES python3 -P dev/prelude-check.py
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-LIST-REMOVE'; exit 1; fi
printf '%s\n' 'PASS M1-LIST-REMOVE'
