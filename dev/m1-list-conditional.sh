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
  row "$work/unit.txt" 'PASS LIST-CONDITIONAL-UNIT cases=74' || missing=1
  row "$work/tests.txt" 'PASS LIST-CONDITIONAL-ARTIFACTS pairs=18' || missing=1
  row "$work/tests.txt" 'PASS LIST-CONDITIONAL-REFUSALS cases=36 atomic_output=36' || missing=1
  row "$work/tests.txt" 'PASS LIST-CONDITIONAL-ORACLES store=45 luajit=45' || missing=1
  row "$work/tests.txt" 'PASS LIST-CONDITIONAL-E2E cases=53 hosts=118 utf8_refusals=2 errors=4 expired=8' || missing=1
  row "$work/tests.txt" 'PASS LIST-CONDITIONAL-EXAMPLE exec=12' || missing=1
  row "$work/tests.txt" 'PASS LIST-CONDITIONAL-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS LIST-CONDITIONAL-MUTATIONS killed=18 survived=0 restored=5' || missing=1
  return "$missing"
}
leg M1-HASH-CONDITIONAL sh dev/m1-hash-conditional.sh
if dune build -j 2 bin/tether.exe dev/store_run.exe dev/list_conditional_tests.exe; then
  printf '%s\n' 'PASS LIST-CONDITIONAL-BUILD'
  leg LIST-CONDITIONAL-UNIT-EXE capture "$work/unit.txt" _build/default/dev/list_conditional_tests.exe
  leg LIST-CONDITIONAL-TESTS-RUN capture "$work/tests.txt" python3 -P dev/list-conditional-tests.py
  leg LIST-CONDITIONAL-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/list-conditional-mutations.py
  leg LIST-CONDITIONAL-COUNTS counts
else
  printf '%s\n' 'FAIL LIST-CONDITIONAL-BUILD'
  failed=1
  for name in LIST-CONDITIONAL-UNIT-EXE LIST-CONDITIONAL-TESTS-RUN LIST-CONDITIONAL-MUTATIONS-RUN LIST-CONDITIONAL-COUNTS; do
    printf 'SKIPPED %s after a red LIST-CONDITIONAL-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg PRELUDES python3 -P dev/prelude-check.py
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-LIST-CONDITIONAL'; exit 1; fi
printf '%s\n' 'PASS M1-LIST-CONDITIONAL'
