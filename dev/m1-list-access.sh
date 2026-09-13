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
  row "$work/unit.txt" 'PASS LIST-ACCESS-UNIT cases=83' &&
  row "$work/tests.txt" 'PASS LIST-ACCESS-ARTIFACTS pairs=19' &&
  row "$work/tests.txt" 'PASS LIST-ACCESS-REFUSALS cases=28 atomic_output=28' &&
  row "$work/tests.txt" 'PASS LIST-ACCESS-ORACLES store=49 luajit=49' &&
  row "$work/tests.txt" 'PASS LIST-ACCESS-E2E cases=49 hosts=98 readonly=38 utf8_refusals=2' &&
  row "$work/tests.txt" 'PASS LIST-ACCESS-EXAMPLE exec=6' &&
  row "$work/mutations.txt" 'PASS LIST-ACCESS-MUTATIONS killed=12 survived=0 restored=6'
}
leg M1-LISTS sh dev/m1-lists.sh
if dune build bin/tether.exe dev/store_run.exe dev/list_access_tests.exe; then
  printf '%s\n' 'PASS LIST-ACCESS-BUILD'
  leg LIST-ACCESS-UNIT-EXE capture "$work/unit.txt" _build/default/dev/list_access_tests.exe
  leg LIST-ACCESS-TESTS-RUN capture "$work/tests.txt" python3 -P dev/list-access-tests.py
  leg LIST-ACCESS-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/list-access-mutations.py
  leg LIST-ACCESS-COUNTS counts
else
  printf '%s\n' 'FAIL LIST-ACCESS-BUILD'
  failed=1
  for name in LIST-ACCESS-UNIT-EXE LIST-ACCESS-TESTS-RUN LIST-ACCESS-MUTATIONS-RUN LIST-ACCESS-COUNTS; do
    printf 'SKIPPED %s after a red LIST-ACCESS-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-LIST-ACCESS'; exit 1; fi
printf '%s\n' 'PASS M1-LIST-ACCESS'
