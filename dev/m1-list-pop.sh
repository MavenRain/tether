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
  row "$work/unit.txt" 'PASS LIST-POP-UNIT cases=109' || missing=1
  row "$work/tests.txt" 'PASS LIST-POP-ARTIFACTS pairs=19' || missing=1
  row "$work/tests.txt" 'PASS LIST-POP-REFUSALS cases=14 atomic_output=14' || missing=1
  row "$work/tests.txt" 'PASS LIST-POP-ORACLES store=69 luajit=69' || missing=1
  row "$work/tests.txt" 'PASS LIST-POP-E2E cases=73 hosts=146 utf8_refusals=4 errors=2 expired=4' || missing=1
  row "$work/tests.txt" 'PASS LIST-POP-EXAMPLE exec=12' || missing=1
  row "$work/tests.txt" 'PASS LIST-POP-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS LIST-POP-MUTATIONS killed=13 survived=0 restored=4' || missing=1
  return "$missing"
}
leg M1-LIST-MOVE sh dev/m1-list-move.sh
if dune build -j 2 bin/tether.exe dev/store_run.exe dev/list_pop_tests.exe; then
  printf '%s\n' 'PASS LIST-POP-BUILD'
  leg LIST-POP-UNIT-EXE capture "$work/unit.txt" _build/default/dev/list_pop_tests.exe
  leg LIST-POP-TESTS-RUN capture "$work/tests.txt" python3 -P dev/list-pop-tests.py
  leg LIST-POP-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/list-pop-mutations.py
  leg LIST-POP-COUNTS counts
else
  printf '%s\n' 'FAIL LIST-POP-BUILD'
  failed=1
  for name in LIST-POP-UNIT-EXE LIST-POP-TESTS-RUN LIST-POP-MUTATIONS-RUN LIST-POP-COUNTS; do
    printf 'SKIPPED %s after a red LIST-POP-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg PRELUDES python3 -P dev/prelude-check.py
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-LIST-POP'; exit 1; fi
printf '%s\n' 'PASS M1-LIST-POP'
