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
  row "$work/unit.txt" 'PASS SET-MEMBERS-UNIT cases=14' || missing=1
  row "$work/tests.txt" 'PASS SET-MEMBERS-ARTIFACTS pairs=6' || missing=1
  row "$work/tests.txt" 'PASS SET-MEMBERS-REFUSALS cases=6 atomic_output=6' || missing=1
  row "$work/tests.txt" 'PASS SET-MEMBERS-ORACLES store=16 luajit=16' || missing=1
  row "$work/tests.txt" 'PASS SET-MEMBERS-E2E cases=18 hosts=38 readonly=32 utf8_refusals=2 errors=2' || missing=1
  row "$work/tests.txt" 'PASS SET-MEMBERS-EXAMPLE exec=6' || missing=1
  row "$work/tests.txt" 'PASS SET-MEMBERS-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS SET-MEMBERS-MUTATIONS killed=9 survived=0 restored=4' || missing=1
  return "$missing"
}
leg M1-LIST-RANGE sh dev/m1-list-range.sh
if dune build bin/tether.exe dev/store_run.exe dev/set_members_tests.exe; then
  printf '%s\n' 'PASS SET-MEMBERS-BUILD'
  leg SET-MEMBERS-UNIT-EXE capture "$work/unit.txt" _build/default/dev/set_members_tests.exe
  leg SET-MEMBERS-TESTS-RUN capture "$work/tests.txt" python3 -P dev/set-members-tests.py
  leg SET-MEMBERS-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/set-members-mutations.py
  leg SET-MEMBERS-COUNTS counts
else
  printf '%s\n' 'FAIL SET-MEMBERS-BUILD'
  failed=1
  for name in SET-MEMBERS-UNIT-EXE SET-MEMBERS-TESTS-RUN SET-MEMBERS-MUTATIONS-RUN SET-MEMBERS-COUNTS; do
    printf 'SKIPPED %s after a red SET-MEMBERS-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-SET-MEMBERS'; exit 1; fi
printf '%s\n' 'PASS M1-SET-MEMBERS'
