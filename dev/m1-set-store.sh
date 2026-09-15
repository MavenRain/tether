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
  row "$work/unit.txt" 'PASS SET-STORE-UNIT cases=322' || missing=1
  row "$work/tests.txt" 'PASS SET-STORE-ARTIFACTS pairs=33' || missing=1
  row "$work/tests.txt" 'PASS SET-STORE-REFUSALS cases=54 atomic_output=54' || missing=1
  row "$work/tests.txt" 'PASS SET-STORE-STORE-EXAMPLE cases=3' || missing=1
  row "$work/tests.txt" 'PASS SET-STORE-ORACLES luajit=201' || missing=1
  row "$work/tests.txt" 'PASS SET-STORE-E2E cases=279 hosts=564 errors=6' || missing=1
  row "$work/tests.txt" 'PASS SET-STORE-EXAMPLE exec=9' || missing=1
  row "$work/tests.txt" 'PASS SET-STORE-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS SET-STORE-MUTATIONS killed=18 survived=0 restored=6' || missing=1
  return "$missing"
}
leg M1-SET-ALGEBRA sh dev/m1-set-algebra.sh
if dune build bin/tether.exe dev/store_run.exe dev/set_store_tests.exe; then
  printf '%s\n' 'PASS SET-STORE-BUILD'
  leg SET-STORE-UNIT-EXE capture "$work/unit.txt" _build/default/dev/set_store_tests.exe
  leg SET-STORE-TESTS-RUN capture "$work/tests.txt" python3 -P dev/set-store-tests.py
  leg SET-STORE-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/set-store-mutations.py
  leg SET-STORE-COUNTS counts
else
  printf '%s\n' 'FAIL SET-STORE-BUILD'
  failed=1
  for name in SET-STORE-UNIT-EXE SET-STORE-TESTS-RUN SET-STORE-MUTATIONS-RUN SET-STORE-COUNTS; do
    printf 'SKIPPED %s after a red SET-STORE-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
leg PRELUDES shasum -a 256 -c dev/PRELUDES.sha256
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-SET-STORE'; exit 1; fi
printf '%s\n' 'PASS M1-SET-STORE'
