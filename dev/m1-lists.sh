#!/bin/sh
set -u
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root" || exit 1
failed=0
work=${TMPDIR:-/tmp}/m1-lists-$$
mkdir -p "$work" || exit 1
trap 'rm -rf "$work"' EXIT INT TERM HUP
leg() {
  name=$1; shift
  if "$@"; then printf 'PASS %s\n' "$name"
  else printf 'FAIL %s\n' "$name"; failed=1
  fi
}
# A red build leaves a stale executable, so the dependent legs report FAIL
# instead of answering from the previous build.
skipped() {
  printf 'SKIPPED %s after a red LISTS-BUILD\n' "$1"
  printf 'FAIL %s\n' "$1"
  failed=1
}
# The suite rows carry the counts, so each suite writes its rows to a file
# that the LISTS-COUNTS leg reads.
capture() {
  out=$1; shift
  "$@" > "$out" 2>&1
  status=$?
  cat "$out"
  return $status
}
row() {
  while IFS= read -r line; do
    if [ "$line" = "$2" ]; then return 0; fi
  done < "$1"
  printf 'MISSING ROW %s\n' "$2"
  return 1
}
counts() {
  row "$work/unit.txt" 'PASS LISTS-UNIT cases=55' &&
  row "$work/tests.txt" 'PASS LISTS-ARTIFACTS pairs=9' &&
  row "$work/tests.txt" 'PASS LISTS-REFUSALS cases=32 atomic_output=32' &&
  row "$work/tests.txt" 'PASS LISTS-ORACLES store=42 luajit=42' &&
  row "$work/tests.txt" 'PASS LISTS-E2E cases=42 hosts=84 readonly=10 utf8_refusals=4' &&
  row "$work/tests.txt" 'PASS LISTS-EXAMPLE exec=9'
}
leg M1-SETS sh dev/m1-sets.sh
if dune build bin/tether.exe dev/store_run.exe dev/lists_tests.exe; then
  printf 'PASS %s\n' 'LISTS-BUILD'
  leg LISTS-UNIT-EXE capture "$work/unit.txt" _build/default/dev/lists_tests.exe
  leg LISTS-TESTS-RUN capture "$work/tests.txt" python3 -P dev/lists-tests.py
  leg LISTS-COUNTS counts
  leg LISTS-MUTATIONS python3 -P dev/lists-mutations.py
else
  printf 'FAIL %s\n' 'LISTS-BUILD'
  failed=1
  skipped LISTS-UNIT-EXE
  skipped LISTS-TESTS-RUN
  skipped LISTS-COUNTS
  skipped LISTS-MUTATIONS
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-LISTS'; exit 1; fi
printf '%s\n' 'PASS M1-LISTS'
