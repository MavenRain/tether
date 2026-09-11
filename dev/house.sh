#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
command -v panicscan > /dev/null 2>&1 || {
  printf '%s\n' 'HOUSE FAIL panicscan is not on PATH'
  exit 1
}
# The glob names every development OCaml source, so a new dev unit cannot
# enter the tree without the house gate.
panicscan --deny present --min present --strict surface print store dev/*.ml
printf '%s\n' 'PASS HOUSE'
