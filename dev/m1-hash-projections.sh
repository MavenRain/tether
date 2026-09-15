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
  row "$work/unit.txt" 'PASS HASH-PROJECTIONS-UNIT cases=36' || missing=1
  row "$work/tests.txt" 'PASS HASH-PROJECTIONS-ARTIFACTS pairs=12' || missing=1
  row "$work/tests.txt" 'PASS HASH-PROJECTIONS-REFUSALS cases=12 atomic_output=12' || missing=1
  row "$work/tests.txt" 'PASS HASH-PROJECTIONS-ORACLES store=38 luajit=38' || missing=1
  row "$work/tests.txt" 'PASS HASH-PROJECTIONS-E2E cases=42 hosts=88 readonly=76 utf8_refusals=6 errors=4' || missing=1
  row "$work/tests.txt" 'PASS HASH-PROJECTIONS-EXAMPLE exec=6' || missing=1
  row "$work/tests.txt" 'PASS HASH-PROJECTIONS-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS HASH-PROJECTIONS-MUTATIONS killed=16 survived=0 restored=6' || missing=1
  return "$missing"
}
leg M1-HASH-ENTRIES sh dev/m1-hash-entries.sh
if dune build bin/tether.exe dev/store_run.exe dev/hash_projections_tests.exe; then
  printf '%s\n' 'PASS HASH-PROJECTIONS-BUILD'
  leg HASH-PROJECTIONS-UNIT-EXE capture "$work/unit.txt" _build/default/dev/hash_projections_tests.exe
  leg HASH-PROJECTIONS-TESTS-RUN capture "$work/tests.txt" python3 -P dev/hash-projections-tests.py
  leg HASH-PROJECTIONS-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/hash-projections-mutations.py
  leg HASH-PROJECTIONS-COUNTS counts
else
  printf '%s\n' 'FAIL HASH-PROJECTIONS-BUILD'
  failed=1
  for name in HASH-PROJECTIONS-UNIT-EXE HASH-PROJECTIONS-TESTS-RUN HASH-PROJECTIONS-MUTATIONS-RUN HASH-PROJECTIONS-COUNTS; do
    printf 'SKIPPED %s after a red HASH-PROJECTIONS-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-HASH-PROJECTIONS'; exit 1; fi
printf '%s\n' 'PASS M1-HASH-PROJECTIONS'
