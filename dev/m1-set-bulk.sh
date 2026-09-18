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
  row "$work/unit.txt" 'PASS SET-BULK-UNIT cases=44' || missing=1
  row "$work/tests.txt" 'PASS SET-BULK-ARTIFACTS pairs=14' || missing=1
  row "$work/tests.txt" 'PASS SET-BULK-REFUSALS cases=20 atomic_output=20' || missing=1
  row "$work/tests.txt" 'PASS SET-BULK-ORACLES store=28 luajit=28' || missing=1
  row "$work/tests.txt" 'PASS SET-BULK-E2E cases=32 hosts=68 utf8_refusals=2 errors=4' || missing=1
  row "$work/tests.txt" 'PASS SET-BULK-EXAMPLE exec=9' || missing=1
  row "$work/tests.txt" 'PASS SET-BULK-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS SET-BULK-MUTATIONS killed=16 survived=0 restored=6' || missing=1
  return "$missing"
}
leg M1-LIST-BULK sh dev/m1-list-bulk.sh
if dune build bin/tether.exe dev/store_run.exe dev/set_bulk_tests.exe; then
  printf '%s\n' 'PASS SET-BULK-BUILD'
  leg SET-BULK-UNIT-EXE capture "$work/unit.txt" _build/default/dev/set_bulk_tests.exe
  leg SET-BULK-TESTS-RUN capture "$work/tests.txt" python3 -P dev/set-bulk-tests.py
  leg SET-BULK-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/set-bulk-mutations.py
  leg SET-BULK-COUNTS counts
else
  printf '%s\n' 'FAIL SET-BULK-BUILD'
  failed=1
  for name in SET-BULK-UNIT-EXE SET-BULK-TESTS-RUN SET-BULK-MUTATIONS-RUN SET-BULK-COUNTS; do
    printf 'SKIPPED %s after a red SET-BULK-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-SET-BULK'; exit 1; fi
printf '%s\n' 'PASS M1-SET-BULK'
