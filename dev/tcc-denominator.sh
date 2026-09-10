#!/bin/zsh
# dev/tcc-denominator.sh [SCRATCH_ROOT]
# Measures the three denominator rows of dev/denominators.json over the four
# C programs of corpus/twin: spine.c, sort.c, parser.c and interp.c.
#
# Rows (S0-D2):
#   tcc_raw_ms_per_kloc        wall time of one command that removes and
#                              recreates the work directory and runs
#                              `tcc -c -o WORK/NAME.o corpus/twin/NAME.c` once
#                              per program, four invocations in sequence.
#   tcc_corrected_ms_per_kloc  the raw median minus the median of the SAME
#                              command shape with every source replaced by
#                              one EMPTY translation unit (rm, mkdir, then
#                              four `tcc -c` on a zero-byte file);  min_ms
#                              and max_ms subtract the same constant.  The
#                              constant is the fixed process cost of the four
#                              `tcc -c` invocations plus the directory reset
#                              and is printed as an informational EMPTY line.
#   trice_end_to_end_ms_per_kloc  the form the trice record measured: one
#                              command that removes and recreates the work
#                              directory, then for each program
#                              `tcc -o WORK/NAME corpus/twin/NAME.c && WORK/NAME`,
#                              so compile, link and run of all four.
# value = median_ms divided by lines over 1000, lines = 1720.
#
# Every timed run starts from a fresh work directory, because the rm and
# mkdir sit inside the timed command.  The timer is dev/bench.sh, which runs
# the command once untimed as a warm-up and then RUNS timed runs (RUNS
# defaults to 5) with perf_counter_ns around one subprocess.
#
# Output: one `LOAD <uptime>` line, one EMPTY line, then exactly three lines
#   DENOM <row> value= median_ms= min_ms= max_ms= runs=5 lines=1720
# No ratio is printed (M0-TCC-RATIO is Stage B or later work).
# Exit codes: 0 on success;  2 when tcc is absent;  3 on a missing input;
# 4 when bench.sh prints no BENCH line.

set -u

ROOT=${0:A:h:h}
TWIN=$ROOT/corpus/twin
BENCH=$ROOT/dev/bench.sh
PROGRAMS=(spine sort parser interp)
RUNS=${RUNS:-5}
SCRATCH_ROOT=${1:-${TMPDIR:-/tmp}}
WORK=$SCRATCH_ROOT/tether-tcc-denominator.$$
OUT=$WORK/out

if ! command -v tcc > /dev/null 2>&1; then
  print -r -- "TCC-ABSENT command -v tcc failed: blocker S0-B3"
  exit 2
fi

if [ ! -f $BENCH ]; then
  print -r -- "TCC-ERROR the timer dev/bench.sh is missing at $BENCH"
  exit 3
fi

LINES=0
RAW_PARTS=()
E2E_PARTS=()
for prog in $PROGRAMS; do
  SRC=$TWIN/$prog.c
  if [ ! -f $SRC ]; then
    print -r -- "TCC-ERROR the twin program $SRC is missing"
    exit 3
  fi
  COUNT=$(wc -l < $SRC | tr -d ' ')
  LINES=$(( LINES + COUNT ))
  RAW_PARTS+=("tcc -c -o $OUT/$prog.o $SRC")
  E2E_PARTS+=("tcc -o $OUT/$prog $SRC")
  E2E_PARTS+=("$OUT/$prog")
done
NPROG=${#PROGRAMS}

mkdir -p $WORK
EMPTY=$WORK/empty.c
: > $EMPTY

FRESH="rm -rf $OUT && mkdir -p $OUT"
RAW_CMD="$FRESH && ${(j: && :)RAW_PARTS}"
EMPTY_PARTS=()
for prog in $PROGRAMS; do
  EMPTY_PARTS+=("tcc -c -o $OUT/empty-$prog.o $EMPTY")
done
EMPTY_CMD="$FRESH && ${(j: && :)EMPTY_PARTS}"
E2E_CMD="$FRESH && ${(j: && :)E2E_PARTS}"

export RUNS

# bench_line NAME CMD -> prints the BENCH line or exits 4
bench_line() {
  local line
  line=$(zsh "$BENCH" "$1" "$2")
  local code=$?
  if [ $code -ne 0 ]; then
    print -r -- "TCC-ERROR bench.sh exited $code for $1: $line"
    rm -rf $WORK
    exit 4
  fi
  print -r -- "$line"
}

# field KEY LINE -> the value of KEY= in LINE
field() {
  local f
  for f in ${=2}; do
    case $f in
      $1=*) print -r -- "${f#$1=}"; return 0 ;;
    esac
  done
  print -r -- ""
}

# emit ROW MEDIAN MIN MAX RUNS
emit() {
  local value
  value=$(/usr/bin/awk -v median=$2 -v lines=$LINES 'BEGIN { printf "%.3f", median / (lines / 1000.0) }')
  print -r -- "DENOM $1 value=$value median_ms=$2 min_ms=$3 max_ms=$4 runs=$5 lines=$LINES"
}

print -r -- "LOAD $(uptime)"

RAW_LINE=$(bench_line tcc_raw "$RAW_CMD") || exit 4
EMPTY_LINE=$(bench_line tcc_empty_tu "$EMPTY_CMD") || exit 4
E2E_LINE=$(bench_line trice_end_to_end "$E2E_CMD") || exit 4
rm -rf $WORK

RAW_MED=$(field median_ms "$RAW_LINE")
RAW_MIN=$(field min_ms "$RAW_LINE")
RAW_MAX=$(field max_ms "$RAW_LINE")
RAW_RUNS=$(field runs "$RAW_LINE")
EMPTY_MED=$(field median_ms "$EMPTY_LINE")
EMPTY_MIN=$(field min_ms "$EMPTY_LINE")
EMPTY_MAX=$(field max_ms "$EMPTY_LINE")
E2E_MED=$(field median_ms "$E2E_LINE")
E2E_MIN=$(field min_ms "$E2E_LINE")
E2E_MAX=$(field max_ms "$E2E_LINE")
E2E_RUNS=$(field runs "$E2E_LINE")

if [ -z "$RAW_MED" ] || [ -z "$EMPTY_MED" ] || [ -z "$E2E_MED" ] || [ -z "$RAW_RUNS" ] || [ -z "$E2E_RUNS" ]; then
  print -r -- "TCC-ERROR bench.sh printed no BENCH line: $RAW_LINE | $EMPTY_LINE | $E2E_LINE"
  exit 4
fi

FIXED=$EMPTY_MED
COR_MED=$(/usr/bin/awk -v r=$RAW_MED -v f=$FIXED 'BEGIN { printf "%.3f", r - f }')
COR_MIN=$(/usr/bin/awk -v r=$RAW_MIN -v f=$FIXED 'BEGIN { printf "%.3f", r - f }')
COR_MAX=$(/usr/bin/awk -v r=$RAW_MAX -v f=$FIXED 'BEGIN { printf "%.3f", r - f }')

print -r -- "EMPTY tcc_empty_tu median_ms=$EMPTY_MED min_ms=$EMPTY_MIN max_ms=$EMPTY_MAX runs=$RAW_RUNS invocations=$NPROG fixed_ms=$FIXED"
emit tcc_raw_ms_per_kloc $RAW_MED $RAW_MIN $RAW_MAX $RAW_RUNS
emit tcc_corrected_ms_per_kloc $COR_MED $COR_MIN $COR_MAX $RAW_RUNS
emit trice_end_to_end_ms_per_kloc $E2E_MED $E2E_MIN $E2E_MAX $E2E_RUNS
exit 0
