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
  row "$work/unit.txt" 'PASS HASH-ENTRIES-UNIT cases=16' || missing=1
  row "$work/tests.txt" 'PASS HASH-ENTRIES-ARTIFACTS pairs=7' || missing=1
  row "$work/tests.txt" 'PASS HASH-ENTRIES-REFUSALS cases=6 atomic_output=6' || missing=1
  row "$work/tests.txt" 'PASS HASH-ENTRIES-ORACLES store=19 luajit=19' || missing=1
  row "$work/tests.txt" 'PASS HASH-ENTRIES-E2E cases=21 hosts=44 readonly=38 utf8_refusals=4 errors=2' || missing=1
  row "$work/tests.txt" 'PASS HASH-ENTRIES-EXAMPLE exec=6' || missing=1
  row "$work/tests.txt" 'PASS HASH-ENTRIES-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS HASH-ENTRIES-MUTATIONS killed=11 survived=0 restored=4' || missing=1
  return "$missing"
}
leg M1-SET-MEMBERS sh dev/m1-set-members.sh
if dune build bin/tether.exe dev/store_run.exe dev/hash_entries_tests.exe; then
  printf '%s\n' 'PASS HASH-ENTRIES-BUILD'
  leg HASH-ENTRIES-UNIT-EXE capture "$work/unit.txt" _build/default/dev/hash_entries_tests.exe
  leg HASH-ENTRIES-TESTS-RUN capture "$work/tests.txt" python3 -P dev/hash-entries-tests.py
  leg HASH-ENTRIES-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/hash-entries-mutations.py
  leg HASH-ENTRIES-COUNTS counts
else
  printf '%s\n' 'FAIL HASH-ENTRIES-BUILD'
  failed=1
  for name in HASH-ENTRIES-UNIT-EXE HASH-ENTRIES-TESTS-RUN HASH-ENTRIES-MUTATIONS-RUN HASH-ENTRIES-COUNTS; do
    printf 'SKIPPED %s after a red HASH-ENTRIES-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-HASH-ENTRIES'; exit 1; fi
printf '%s\n' 'PASS M1-HASH-ENTRIES'
