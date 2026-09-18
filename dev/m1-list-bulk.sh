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
  row "$work/unit.txt" 'PASS LIST-BULK-UNIT cases=40' || missing=1
  row "$work/tests.txt" 'PASS LIST-BULK-ARTIFACTS pairs=13' || missing=1
  row "$work/tests.txt" 'PASS LIST-BULK-REFUSALS cases=20 atomic_output=20' || missing=1
  row "$work/tests.txt" 'PASS LIST-BULK-ORACLES store=23 luajit=23' || missing=1
  row "$work/tests.txt" 'PASS LIST-BULK-E2E cases=27 hosts=56 utf8_refusals=2 errors=2' || missing=1
  row "$work/tests.txt" 'PASS LIST-BULK-EXAMPLE exec=9' || missing=1
  row "$work/tests.txt" 'PASS LIST-BULK-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS LIST-BULK-MUTATIONS killed=16 survived=0 restored=6' || missing=1
  return "$missing"
}
leg M1-HMGET sh dev/m1-hmget.sh
if dune build bin/tether.exe dev/store_run.exe dev/list_bulk_tests.exe; then
  printf '%s\n' 'PASS LIST-BULK-BUILD'
  leg LIST-BULK-UNIT-EXE capture "$work/unit.txt" _build/default/dev/list_bulk_tests.exe
  leg LIST-BULK-TESTS-RUN capture "$work/tests.txt" python3 -P dev/list-bulk-tests.py
  leg LIST-BULK-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/list-bulk-mutations.py
  leg LIST-BULK-COUNTS counts
else
  printf '%s\n' 'FAIL LIST-BULK-BUILD'
  failed=1
  for name in LIST-BULK-UNIT-EXE LIST-BULK-TESTS-RUN LIST-BULK-MUTATIONS-RUN LIST-BULK-COUNTS; do
    printf 'SKIPPED %s after a red LIST-BULK-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-LIST-BULK'; exit 1; fi
printf '%s\n' 'PASS M1-LIST-BULK'
