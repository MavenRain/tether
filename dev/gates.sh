#!/bin/sh
set -u
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root" || exit 1
failed=0
leg() {
  name=$1; shift
  if "$@"; then printf 'PASS %s\n' "$name"
  else printf 'FAIL %s\n' "$name"; failed=1
  fi
}
leg STAGE-E sh dev/stage-e.sh
leg DRIVER-BUILD dune build bin/tether.exe dev/bytes_probe.exe
leg STAGE-F-TESTS python3 -P dev/stage-f-tests.py
leg PASSES ./tether check examples/M0Spine.tet --passes
leg MEASURE sh dev/ratio.sh
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL STAGE-F'; exit 1; fi
printf '%s\n' 'PASS STAGE-F'
