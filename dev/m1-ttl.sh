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
  row "$work/unit.txt" 'PASS TTL-UNIT cases=146' || missing=1
  row "$work/tests.txt" 'PASS TTL-ORACLES store=34 luajit=35' || missing=1
  row "$work/tests.txt" 'PASS TTL-CLOCK cases=3' || missing=1
  row "$work/tests.txt" 'PASS TTL-REFUSALS cases=5' || missing=1
  row "$work/tests.txt" 'PASS TTL-E2E cases=35 hosts=70' || missing=1
  row "$work/tests.txt" 'PASS TTL-EXAMPLE hosts=3' || missing=1
  row "$work/tests.txt" 'PASS TTL-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS TTL-MUTATIONS killed=13 survived=0 restored=5' || missing=1
  return "$missing"
}
leg M1-SET-MOVE sh dev/m1-set-move.sh
if dune build bin/tether.exe dev/store_run.exe dev/ttl_tests.exe; then
  printf '%s\n' 'PASS TTL-BUILD'
  leg TTL-UNIT-EXE capture "$work/unit.txt" _build/default/dev/ttl_tests.exe
  leg TTL-TESTS-RUN capture "$work/tests.txt" python3 -P dev/ttl-tests.py
  leg TTL-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/ttl-mutations.py
  leg TTL-COUNTS counts
else
  printf '%s\n' 'FAIL TTL-BUILD'
  failed=1
  for name in TTL-UNIT-EXE TTL-TESTS-RUN TTL-MUTATIONS-RUN TTL-COUNTS; do
    printf 'SKIPPED %s after a red TTL-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
leg PRELUDES shasum -a 256 -c dev/PRELUDES.sha256
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-TTL'; exit 1; fi
printf '%s\n' 'PASS M1-TTL'
