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
  row "$work/unit.txt" 'PASS HSET-MANY-UNIT cases=43' || missing=1
  row "$work/tests.txt" 'PASS HSET-MANY-ARTIFACTS pairs=9' || missing=1
  row "$work/tests.txt" 'PASS HSET-MANY-REFUSALS cases=14 atomic_output=14' || missing=1
  row "$work/tests.txt" 'PASS HSET-MANY-ORACLES store=23 luajit=23' || missing=1
  row "$work/tests.txt" 'PASS HSET-MANY-E2E cases=25 hosts=52 utf8_refusals=2 errors=2' || missing=1
  row "$work/tests.txt" 'PASS HSET-MANY-EXAMPLE exec=9' || missing=1
  row "$work/tests.txt" 'PASS HSET-MANY-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS HSET-MANY-MUTATIONS killed=16 survived=0 restored=6' || missing=1
  return "$missing"
}
leg M1-HDEL-MANY sh dev/m1-hdel-many.sh
if dune build bin/tether.exe dev/store_run.exe dev/hset_many_tests.exe; then
  printf '%s\n' 'PASS HSET-MANY-BUILD'
  leg HSET-MANY-UNIT-EXE capture "$work/unit.txt" _build/default/dev/hset_many_tests.exe
  leg HSET-MANY-TESTS-RUN capture "$work/tests.txt" python3 -P dev/hset-many-tests.py
  leg HSET-MANY-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/hset-many-mutations.py
  leg HSET-MANY-COUNTS counts
else
  printf '%s\n' 'FAIL HSET-MANY-BUILD'
  failed=1
  for name in HSET-MANY-UNIT-EXE HSET-MANY-TESTS-RUN HSET-MANY-MUTATIONS-RUN HSET-MANY-COUNTS; do
    printf 'SKIPPED %s after a red HSET-MANY-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg PRELUDES python3 -P dev/prelude-check.py
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-HSET-MANY'; exit 1; fi
printf '%s\n' 'PASS M1-HSET-MANY'
