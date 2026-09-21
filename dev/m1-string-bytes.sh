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
  row "$work/unit.txt" 'PASS STRING-BYTES-UNIT cases=60' || missing=1
  row "$work/tests.txt" 'PASS STRING-BYTES-ARTIFACTS pairs=11' || missing=1
  row "$work/tests.txt" 'PASS STRING-BYTES-REFUSALS cases=15 atomic_output=15' || missing=1
  row "$work/tests.txt" 'PASS STRING-BYTES-ORACLES store=45 luajit=45' || missing=1
  row "$work/tests.txt" 'PASS STRING-BYTES-E2E cases=51 hosts=102 errors=4 expired=4' || missing=1
  row "$work/tests.txt" 'PASS STRING-BYTES-EXAMPLE exec=12' || missing=1
  row "$work/tests.txt" 'PASS STRING-BYTES-TESTS' || missing=1
  row "$work/mutations.txt" 'PASS STRING-BYTES-MUTATIONS killed=15 survived=0 restored=3' || missing=1
  return "$missing"
}
leg M1-LIST-POP sh dev/m1-list-pop.sh
if dune build -j 2 bin/tether.exe dev/store_run.exe dev/string_bytes_tests.exe; then
  printf '%s\n' 'PASS STRING-BYTES-BUILD'
  leg STRING-BYTES-UNIT-EXE capture "$work/unit.txt" _build/default/dev/string_bytes_tests.exe
  leg STRING-BYTES-TESTS-RUN capture "$work/tests.txt" python3 -P dev/string-bytes-tests.py
  leg STRING-BYTES-MUTATIONS-RUN capture "$work/mutations.txt" python3 -P dev/string-bytes-mutations.py
  leg STRING-BYTES-COUNTS counts
else
  printf '%s\n' 'FAIL STRING-BYTES-BUILD'
  failed=1
  for name in STRING-BYTES-UNIT-EXE STRING-BYTES-TESTS-RUN STRING-BYTES-MUTATIONS-RUN STRING-BYTES-COUNTS; do
    printf 'SKIPPED %s after a red STRING-BYTES-BUILD\nFAIL %s\n' "$name" "$name"
  done
fi
leg HOUSE sh dev/house.sh
leg PRELUDES python3 -P dev/prelude-check.py
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-STRING-BYTES'; exit 1; fi
printf '%s\n' 'PASS M1-STRING-BYTES'
