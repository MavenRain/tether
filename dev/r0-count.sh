#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
# Rebuild the scoped target so source edits cannot reuse stale counts. An
# absent or broken dune exits 127 under set -e and ends the ladder with the
# shell message alone, so both faces carry their own reason and exit 1.
command -v dune > /dev/null 2>&1 || {
  printf '%s\n' 'R0-COUNT FAIL dune is not on PATH'
  exit 1
}
dune build --root "$root" vendor/kanon/bin/kanon.exe || {
  printf '%s\n' 'R0-COUNT FAIL the scoped dune build failed'
  exit 1
}
exec python3 -P "$root/dev/foundation.py" count "$root"
