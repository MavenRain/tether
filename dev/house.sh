#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
command -v panicscan > /dev/null 2>&1 || {
  printf '%s\n' 'HOUSE FAIL panicscan is not on PATH'
  exit 1
}
panicscan --deny present --min present --strict surface dev/surface_check.ml
printf '%s\n' 'PASS HOUSE'
