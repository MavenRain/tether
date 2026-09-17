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
  row "$work/unit.txt" 'PASS CONDITIONAL-UNIT cases=878' || missing=1
  row "$work/tests.txt" 'PASS CONDITIONAL-ORACLES store=119 luajit=120' || missing=1
  row "$work/tests.txt" 'PASS CONDITIONAL-CLOCK cases=4 store=4' || missing=1
  row "$work/tests.txt" 'PASS CONDITIONAL-REFUSALS cases=8' || missing=1
  row "$work/tests.txt" 'PASS CONDITIONAL-E2E cases=120 hosts=240' || missing=1
  row "$work/tests.txt" 'PASS CONDITIONAL-EXAMPLE hosts=3' || missing=1
  row "$work/tests.txt" 'PASS CONDITIONAL-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS CONDITIONAL-MUTATIONS killed=17 survived=0 restored=10' || missing=1
  return "$missing"
}
leg M1-ABSOLUTE-EXPIRY sh dev/m1-absolute-expiry.sh
if dune build bin/tether.exe dev/store_run.exe dev/conditional_expiry_tests.exe; then
  printf '%s\n' 'PASS CONDITIONAL-BUILD'
  leg CONDITIONAL-UNIT-EXE capture "$work/unit.txt" _build/default/dev/conditional_expiry_tests.exe
  leg CONDITIONAL-TESTS-RUN capture "$work/tests.txt" python3 -P dev/conditional-expiry-tests.py
  leg CONDITIONAL-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/conditional-expiry-mutations.py
  leg CONDITIONAL-COUNTS counts
else
  printf '%s\n' 'FAIL CONDITIONAL-BUILD'
  failed=1
  for name in CONDITIONAL-UNIT-EXE CONDITIONAL-TESTS-RUN CONDITIONAL-MUTATIONS-RUN CONDITIONAL-COUNTS; do
    printf 'SKIPPED %s after a red CONDITIONAL-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
leg PRELUDES shasum -a 256 -c dev/PRELUDES.sha256
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-CONDITIONAL-EXPIRY'; exit 1; fi
printf '%s\n' 'PASS M1-CONDITIONAL-EXPIRY'
