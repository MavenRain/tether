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
  row "$work/unit.txt" 'PASS HMGET-UNIT cases=26' || missing=1
  row "$work/tests.txt" 'PASS HMGET-ARTIFACTS pairs=10' || missing=1
  row "$work/tests.txt" 'PASS HMGET-REFUSALS cases=10 atomic_output=10' || missing=1
  row "$work/tests.txt" 'PASS HMGET-ORACLES store=18 luajit=18' || missing=1
  row "$work/tests.txt" 'PASS HMGET-E2E cases=20 hosts=42 readonly=38 utf8_refusals=2 errors=2' || missing=1
  row "$work/tests.txt" 'PASS HMGET-EXAMPLE exec=6' || missing=1
  row "$work/tests.txt" 'PASS HMGET-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS HMGET-MUTATIONS killed=16 survived=0 restored=6' || missing=1
  return "$missing"
}
leg M1-CONDITIONAL-EXPIRY sh dev/m1-conditional-expiry.sh
if dune build bin/tether.exe dev/store_run.exe dev/hmget_tests.exe; then
  printf '%s\n' 'PASS HMGET-BUILD'
  leg HMGET-UNIT-EXE capture "$work/unit.txt" _build/default/dev/hmget_tests.exe
  leg HMGET-TESTS-RUN capture "$work/tests.txt" python3 -P dev/hmget-tests.py
  leg HMGET-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/hmget-mutations.py
  leg HMGET-COUNTS counts
else
  printf '%s\n' 'FAIL HMGET-BUILD'
  failed=1
  for name in HMGET-UNIT-EXE HMGET-TESTS-RUN HMGET-MUTATIONS-RUN HMGET-COUNTS; do
    printf 'SKIPPED %s after a red HMGET-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-HMGET'; exit 1; fi
printf '%s\n' 'PASS M1-HMGET'
