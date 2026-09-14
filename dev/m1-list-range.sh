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
  row "$work/unit.txt" 'PASS LIST-RANGE-UNIT cases=101' &&
  row "$work/tests.txt" 'PASS LIST-RANGE-ARTIFACTS pairs=18' &&
  row "$work/tests.txt" 'PASS LIST-RANGE-REFUSALS cases=18 atomic_output=18' &&
  row "$work/tests.txt" 'PASS LIST-RANGE-ORACLES store=40 luajit=40' &&
  row "$work/tests.txt" 'PASS LIST-RANGE-DRIVER replies=8' &&
  row "$work/tests.txt" 'PASS LIST-RANGE-E2E cases=42 hosts=86 readonly=82 utf8_refusals=2 errors=2' &&
  row "$work/tests.txt" 'PASS LIST-RANGE-EXAMPLE exec=6' &&
  row "$work/tests.txt" 'PASS LIST-RANGE-TESTS' &&
  row "$work/mutations.txt" 'PASS LIST-RANGE-MUTATIONS killed=11 survived=0 restored=5'
}
leg M1-LIST-ACCESS sh dev/m1-list-access.sh
if dune build bin/tether.exe dev/store_run.exe dev/list_range_tests.exe; then
  printf '%s\n' 'PASS LIST-RANGE-BUILD'
  leg LIST-RANGE-UNIT-EXE capture "$work/unit.txt" _build/default/dev/list_range_tests.exe
  leg LIST-RANGE-TESTS-RUN capture "$work/tests.txt" python3 -P dev/list-range-tests.py
  leg LIST-RANGE-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/list-range-mutations.py
  leg LIST-RANGE-COUNTS counts
else
  printf '%s\n' 'FAIL LIST-RANGE-BUILD'
  failed=1
  for name in LIST-RANGE-UNIT-EXE LIST-RANGE-TESTS-RUN LIST-RANGE-MUTATIONS-RUN LIST-RANGE-COUNTS; do
    printf 'SKIPPED %s after a red LIST-RANGE-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-LIST-RANGE'; exit 1; fi
printf '%s\n' 'PASS M1-LIST-RANGE'
