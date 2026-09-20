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
  row "$work/unit.txt" 'PASS LIST-INSERT-UNIT cases=50' || missing=1
  row "$work/tests.txt" 'PASS LIST-INSERT-ARTIFACTS pairs=17' || missing=1
  row "$work/tests.txt" 'PASS LIST-INSERT-REFUSALS cases=16 atomic_output=16' || missing=1
  row "$work/tests.txt" 'PASS LIST-INSERT-ORACLES store=31 luajit=31' || missing=1
  row "$work/tests.txt" 'PASS LIST-INSERT-E2E cases=35 hosts=78 utf8_refusals=2 errors=4 expired=4' || missing=1
  row "$work/tests.txt" 'PASS LIST-INSERT-EXAMPLE exec=9' || missing=1
  row "$work/tests.txt" 'PASS LIST-INSERT-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS LIST-INSERT-MUTATIONS killed=14 survived=0 restored=5' || missing=1
  return "$missing"
}
leg M1-LIST-REMOVE sh dev/m1-list-remove.sh
if dune build -j 2 bin/tether.exe dev/store_run.exe dev/list_insert_tests.exe; then
  printf '%s\n' 'PASS LIST-INSERT-BUILD'
  leg LIST-INSERT-UNIT-EXE capture "$work/unit.txt" _build/default/dev/list_insert_tests.exe
  leg LIST-INSERT-TESTS-RUN capture "$work/tests.txt" python3 -P dev/list-insert-tests.py
  leg LIST-INSERT-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/list-insert-mutations.py
  leg LIST-INSERT-COUNTS counts
else
  printf '%s\n' 'FAIL LIST-INSERT-BUILD'
  failed=1
  for name in LIST-INSERT-UNIT-EXE LIST-INSERT-TESTS-RUN LIST-INSERT-MUTATIONS-RUN LIST-INSERT-COUNTS; do
    printf 'SKIPPED %s after a red LIST-INSERT-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg PRELUDES python3 -P dev/prelude-check.py
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-LIST-INSERT'; exit 1; fi
printf '%s\n' 'PASS M1-LIST-INSERT'
