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
leg M1-DO sh dev/m1-do.sh
leg RO-HOSTS node --test dev/readonly-host-tests.mjs
leg RO-TESTS python3 -P dev/readonly-tests.py
leg RO-MUTATIONS python3 -P dev/readonly-mutations.py
leg TRUSTED-LINES python3 -P dev/trusted-lines.py
if [ "$failed" -ne 0 ]; then printf '%s\n' 'FAIL M1-READONLY'; exit 1; fi
printf '%s\n' 'PASS M1-READONLY'
