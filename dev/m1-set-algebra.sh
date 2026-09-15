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
  row "$work/unit.txt" 'PASS SET-ALGEBRA-UNIT cases=106' || missing=1
  row "$work/tests.txt" 'PASS SET-ALGEBRA-ARTIFACTS pairs=24' || missing=1
  row "$work/tests.txt" 'PASS SET-ALGEBRA-REFUSALS cases=36 atomic_output=36' || missing=1
  row "$work/tests.txt" 'PASS SET-ALGEBRA-STORE-EXAMPLE cases=4' || missing=1
  row "$work/tests.txt" 'PASS SET-ALGEBRA-ORACLES luajit=90' || missing=1
  row "$work/tests.txt" 'PASS SET-ALGEBRA-E2E cases=114 hosts=234 readonly=216 utf8_refusals=6 errors=6' || missing=1
  row "$work/tests.txt" 'PASS SET-ALGEBRA-EXAMPLE exec=12' || missing=1
  row "$work/tests.txt" 'PASS SET-ALGEBRA-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS SET-ALGEBRA-MUTATIONS killed=17 survived=0 restored=6' || missing=1
  return "$missing"
}
leg M1-HASH-PROJECTIONS sh dev/m1-hash-projections.sh
if dune build bin/tether.exe dev/store_run.exe dev/set_algebra_tests.exe; then
  printf '%s\n' 'PASS SET-ALGEBRA-BUILD'
  leg SET-ALGEBRA-UNIT-EXE capture "$work/unit.txt" _build/default/dev/set_algebra_tests.exe
  leg SET-ALGEBRA-TESTS-RUN capture "$work/tests.txt" python3 -P dev/set-algebra-tests.py
  leg SET-ALGEBRA-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/set-algebra-mutations.py
  leg SET-ALGEBRA-COUNTS counts
else
  printf '%s\n' 'FAIL SET-ALGEBRA-BUILD'
  failed=1
  for name in SET-ALGEBRA-UNIT-EXE SET-ALGEBRA-TESTS-RUN SET-ALGEBRA-MUTATIONS-RUN SET-ALGEBRA-COUNTS; do
    printf 'SKIPPED %s after a red SET-ALGEBRA-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
leg PRELUDES shasum -a 256 -c dev/PRELUDES.sha256
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-SET-ALGEBRA'; exit 1; fi
printf '%s\n' 'PASS M1-SET-ALGEBRA'
