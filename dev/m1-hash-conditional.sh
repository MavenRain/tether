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
  row "$work/unit.txt" 'PASS HASH-CONDITIONAL-UNIT cases=32' || missing=1
  row "$work/tests.txt" 'PASS HASH-CONDITIONAL-ARTIFACTS pairs=13' || missing=1
  row "$work/tests.txt" 'PASS HASH-CONDITIONAL-REFUSALS cases=15 atomic_output=15' || missing=1
  row "$work/tests.txt" 'PASS HASH-CONDITIONAL-ORACLES store=34 luajit=34' || missing=1
  row "$work/tests.txt" 'PASS HASH-CONDITIONAL-E2E cases=38 hosts=80 errors=4' || missing=1
  row "$work/tests.txt" 'PASS HASH-CONDITIONAL-EXAMPLE exec=9' || missing=1
  row "$work/tests.txt" 'PASS HASH-CONDITIONAL-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS HASH-CONDITIONAL-MUTATIONS killed=13 survived=0 restored=3' || missing=1
  return "$missing"
}
leg M1-HSET-MANY sh dev/m1-hset-many.sh
if dune build -j 2 bin/tether.exe dev/store_run.exe dev/hash_conditional_tests.exe; then
  printf '%s\n' 'PASS HASH-CONDITIONAL-BUILD'
  leg HASH-CONDITIONAL-UNIT-EXE capture "$work/unit.txt" _build/default/dev/hash_conditional_tests.exe
  leg HASH-CONDITIONAL-TESTS-RUN capture "$work/tests.txt" python3 -P dev/hash-conditional-tests.py
  leg HASH-CONDITIONAL-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/hash-conditional-mutations.py
  leg HASH-CONDITIONAL-COUNTS counts
else
  printf '%s\n' 'FAIL HASH-CONDITIONAL-BUILD'
  failed=1
  for name in HASH-CONDITIONAL-UNIT-EXE HASH-CONDITIONAL-TESTS-RUN HASH-CONDITIONAL-MUTATIONS-RUN HASH-CONDITIONAL-COUNTS; do
    printf 'SKIPPED %s after a red HASH-CONDITIONAL-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg PRELUDES python3 -P dev/prelude-check.py
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-HASH-CONDITIONAL'; exit 1; fi
printf '%s\n' 'PASS M1-HASH-CONDITIONAL'
