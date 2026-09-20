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
  row "$work/unit.txt" 'PASS LIST-MOVE-UNIT cases=104' || missing=1
  row "$work/tests.txt" 'PASS LIST-MOVE-ARTIFACTS pairs=14' || missing=1
  row "$work/tests.txt" 'PASS LIST-MOVE-REFUSALS cases=18 atomic_output=18' || missing=1
  row "$work/tests.txt" 'PASS LIST-MOVE-ORACLES store=48 luajit=48' || missing=1
  row "$work/tests.txt" 'PASS LIST-MOVE-E2E cases=52 hosts=104 utf8_refusals=2 errors=4 expired=6' || missing=1
  row "$work/tests.txt" 'PASS LIST-MOVE-EXAMPLE exec=9' || missing=1
  row "$work/tests.txt" 'PASS LIST-MOVE-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS LIST-MOVE-MUTATIONS killed=14 survived=0 restored=5' || missing=1
  return "$missing"
}
leg M1-LIST-INSERT sh dev/m1-list-insert.sh
if dune build -j 2 bin/tether.exe dev/store_run.exe dev/list_move_tests.exe; then
  printf '%s\n' 'PASS LIST-MOVE-BUILD'
  leg LIST-MOVE-UNIT-EXE capture "$work/unit.txt" _build/default/dev/list_move_tests.exe
  leg LIST-MOVE-TESTS-RUN capture "$work/tests.txt" python3 -P dev/list-move-tests.py
  leg LIST-MOVE-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/list-move-mutations.py
  leg LIST-MOVE-COUNTS counts
else
  printf '%s\n' 'FAIL LIST-MOVE-BUILD'
  failed=1
  for name in LIST-MOVE-UNIT-EXE LIST-MOVE-TESTS-RUN LIST-MOVE-MUTATIONS-RUN LIST-MOVE-COUNTS; do
    printf 'SKIPPED %s after a red LIST-MOVE-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg PRELUDES python3 -P dev/prelude-check.py
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-LIST-MOVE'; exit 1; fi
printf '%s\n' 'PASS M1-LIST-MOVE'
