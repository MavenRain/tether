#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
sh dev/carry-check.sh
sh dev/r0-count.sh
sh dev/r0-audit.sh
# The inherited counter builds both counts with awk under set -u alone, so a
# broken awk leaves an empty count that passes the bound. The printed line is
# read here, and an empty count fails the run.
lines=$(zsh -f dev/inherited/trusted-lines.sh "$root/vendor/kanon") || {
  printf '%s\n' "$lines"
  printf '%s\n' 'TRUSTED-LINES FAIL inherited counter exits nonzero'
  exit 1
}
# An sh glob [0-9]* is one digit and any tail, so each count is cut out and
# read as a digit run, and the line is rebuilt and compared with the printed
# one. A non-digit count and a trailing remark both fail here.
kernel=${lines#TRUSTED-LINES kernel=}
kernel=${kernel%%/*}
encoder=${lines##*encoder=}
encoder=${encoder%%/*}
ok=1
case "$kernel" in '' | *[!0-9]*) ok=0 ;; esac
case "$encoder" in '' | *[!0-9]*) ok=0 ;; esac
[ "TRUSTED-LINES kernel=$kernel/4000 encoder=$encoder/600 OK" = "$lines" ] || ok=0
[ "$ok" -eq 1 ] || {
  printf '%s\n' "$lines"
  printf '%s\n' 'TRUSTED-LINES FAIL unexpected line'
  exit 1
}
printf '%s\n' "$lines"
# The checksum check reads the rows the manifest holds, so a manifest with
# rows removed passes over the artifacts it no longer names. The ruled row
# count is eight, and it is read before the rows are checked.
[ -f dev/DENOMINATORS.sha256 ] || {
  printf '%s\n' 'DENOMINATORS FAIL the manifest dev/DENOMINATORS.sha256 is missing'
  exit 1
}
rows=$(wc -l < dev/DENOMINATORS.sha256)
rows=$((rows + 0))
[ "$rows" -eq 8 ] || {
  printf '%s\n' "DENOMINATORS FAIL the manifest holds $rows rows and the ruling fixes 8"
  exit 1
}
# A row count alone leaves the manifest open to a swap: a row replaced by a
# copy of another row keeps the count at eight and drops one artifact from
# the check. The name column is therefore pinned as well. It is read with
# awk, sorted and rebuilt as one line, so a swapped name, a duplicated name
# and an added name all fail. A broken awk leaves an empty list, which
# fails here too.
ruled='corpus/lua/m0-spine.lua corpus/twin/interp.c corpus/twin/parser.c '
ruled=$ruled'corpus/twin/sort.c corpus/twin/spine.c dev/bench.sh '
ruled=$ruled'dev/denominators.json dev/tcc-denominator.sh'
names=$(awk '{ print $NF }' dev/DENOMINATORS.sha256 | LC_ALL=C sort | tr '\n' ' ')
names=${names% }
[ "$names" = "$ruled" ] || {
  printf '%s\n' "DENOMINATORS FAIL the manifest names $names and the ruling fixes $ruled"
  exit 1
}
# A broken or absent shasum exits 127 under set -e and ends the ladder with
# no reason line, so the call carries its own reason and exit 1.
shasum -a 256 -c dev/DENOMINATORS.sha256 || {
  printf '%s\n' 'DENOMINATORS FAIL the checksum check failed or shasum is broken'
  exit 1
}
printf '%s\n' 'PASS STAGE-A'
