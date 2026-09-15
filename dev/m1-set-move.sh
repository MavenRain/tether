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
  row "$work/unit.txt" 'PASS SET-MOVE-UNIT cases=304' || missing=1
  row "$work/tests.txt" 'PASS SET-MOVE-ARTIFACTS pairs=12' || missing=1
  row "$work/tests.txt" 'PASS SET-MOVE-REFUSALS cases=14 atomic_output=14' || missing=1
  row "$work/tests.txt" 'PASS SET-MOVE-STORE-EXAMPLE cases=3' || missing=1
  row "$work/tests.txt" 'PASS SET-MOVE-ORACLES luajit=113' || missing=1
  row "$work/tests.txt" 'PASS SET-MOVE-E2E cases=179 hosts=360 errors=2' || missing=1
  row "$work/tests.txt" 'PASS SET-MOVE-EXAMPLE exec=9' || missing=1
  row "$work/tests.txt" 'PASS SET-MOVE-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS SET-MOVE-MUTATIONS killed=15 survived=0 restored=5' || missing=1
  return "$missing"
}
leg M1-SET-STORE sh dev/m1-set-store.sh
if dune build bin/tether.exe dev/store_run.exe dev/set_move_tests.exe; then
  printf '%s\n' 'PASS SET-MOVE-BUILD'
  leg SET-MOVE-UNIT-EXE capture "$work/unit.txt" _build/default/dev/set_move_tests.exe
  leg SET-MOVE-TESTS-RUN capture "$work/tests.txt" python3 -P dev/set-move-tests.py
  leg SET-MOVE-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/set-move-mutations.py
  leg SET-MOVE-COUNTS counts
else
  printf '%s\n' 'FAIL SET-MOVE-BUILD'
  failed=1
  for name in SET-MOVE-UNIT-EXE SET-MOVE-TESTS-RUN SET-MOVE-MUTATIONS-RUN SET-MOVE-COUNTS; do
    printf 'SKIPPED %s after a red SET-MOVE-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
leg PRELUDES shasum -a 256 -c dev/PRELUDES.sha256
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-SET-MOVE'; exit 1; fi
printf '%s\n' 'PASS M1-SET-MOVE'
