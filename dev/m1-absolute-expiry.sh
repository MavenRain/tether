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
  row "$work/unit.txt" 'PASS ABSOLUTE-UNIT cases=162' || missing=1
  row "$work/tests.txt" 'PASS ABSOLUTE-ORACLES store=37 luajit=38' || missing=1
  row "$work/tests.txt" 'PASS ABSOLUTE-CLOCK cases=6 store=3' || missing=1
  row "$work/tests.txt" 'PASS ABSOLUTE-REFUSALS cases=6' || missing=1
  row "$work/tests.txt" 'PASS ABSOLUTE-E2E cases=38 hosts=76' || missing=1
  row "$work/tests.txt" 'PASS ABSOLUTE-EXAMPLE hosts=3' || missing=1
  row "$work/tests.txt" 'PASS ABSOLUTE-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS ABSOLUTE-MUTATIONS killed=14 survived=0 restored=8' || missing=1
  return "$missing"
}
leg M1-TTL sh dev/m1-ttl.sh
if dune build bin/tether.exe dev/store_run.exe dev/absolute_expiry_tests.exe; then
  printf '%s\n' 'PASS ABSOLUTE-BUILD'
  leg ABSOLUTE-UNIT-EXE capture "$work/unit.txt" _build/default/dev/absolute_expiry_tests.exe
  leg ABSOLUTE-TESTS-RUN capture "$work/tests.txt" python3 -P dev/absolute-expiry-tests.py
  leg ABSOLUTE-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/absolute-expiry-mutations.py
  leg ABSOLUTE-COUNTS counts
else
  printf '%s\n' 'FAIL ABSOLUTE-BUILD'
  failed=1
  for name in ABSOLUTE-UNIT-EXE ABSOLUTE-TESTS-RUN ABSOLUTE-MUTATIONS-RUN ABSOLUTE-COUNTS; do
    printf 'SKIPPED %s after a red ABSOLUTE-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
leg PRELUDES shasum -a 256 -c dev/PRELUDES.sha256
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-ABSOLUTE-EXPIRY'; exit 1; fi
printf '%s\n' 'PASS M1-ABSOLUTE-EXPIRY'
