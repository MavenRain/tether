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
  row "$work/unit.txt" 'PASS HDEL-MANY-UNIT cases=36' || missing=1
  row "$work/tests.txt" 'PASS HDEL-MANY-ARTIFACTS pairs=9' || missing=1
  row "$work/tests.txt" 'PASS HDEL-MANY-REFUSALS cases=10 atomic_output=10' || missing=1
  row "$work/tests.txt" 'PASS HDEL-MANY-ORACLES store=21 luajit=21' || missing=1
  row "$work/tests.txt" 'PASS HDEL-MANY-E2E cases=23 hosts=48 utf8_refusals=2 errors=2' || missing=1
  row "$work/tests.txt" 'PASS HDEL-MANY-EXAMPLE exec=9' || missing=1
  row "$work/tests.txt" 'PASS HDEL-MANY-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS HDEL-MANY-MUTATIONS killed=14 survived=0 restored=5' || missing=1
  return "$missing"
}
leg M1-SET-BULK sh dev/m1-set-bulk.sh
if dune build bin/tether.exe dev/store_run.exe dev/hdel_many_tests.exe; then
  printf '%s\n' 'PASS HDEL-MANY-BUILD'
  leg HDEL-MANY-UNIT-EXE capture "$work/unit.txt" _build/default/dev/hdel_many_tests.exe
  leg HDEL-MANY-TESTS-RUN capture "$work/tests.txt" python3 -P dev/hdel-many-tests.py
  leg HDEL-MANY-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/hdel-many-mutations.py
  leg HDEL-MANY-COUNTS counts
else
  printf '%s\n' 'FAIL HDEL-MANY-BUILD'
  failed=1
  for name in HDEL-MANY-UNIT-EXE HDEL-MANY-TESTS-RUN HDEL-MANY-MUTATIONS-RUN HDEL-MANY-COUNTS; do
    printf 'SKIPPED %s after a red HDEL-MANY-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg PRELUDES python3 -P dev/prelude-check.py
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-HDEL-MANY'; exit 1; fi
printf '%s\n' 'PASS M1-HDEL-MANY'
