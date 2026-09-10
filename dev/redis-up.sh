#!/bin/bash
# dev/redis-up.sh PIDFILE [LOGDIR]
#
# Starts one redis-server on a free loopback port for a gate run (R-Q7, R-M0-8).
# Prints exactly one line on success:
#   REDIS-UP port=<p> pid=<n> pidfile=<path>
# and exits 1 with REDIS-UP FAIL <reason> otherwise.
#
# Free-port method (S0-D4): a candidate port is drawn from 30000..49999 with
# $RANDOM, probed with `lsof -nP -iTCP:<p> -sTCP:LISTEN`, and then confirmed
# by the server itself: the port is only accepted when `redis-cli -p <p> ping`
# prints PONG within the bounded retry.  A bind race moves to the next
# candidate;  at most 20 candidates are tried.
#
# Pidfile convention (S0-D4): the caller names the pidfile as the first
# argument;  the server log is <LOGDIR>/redis-<p>.log where LOGDIR defaults
# to the directory of the pidfile.  Both match the .gitignore rows *.pid and
# *.log, so a pidfile under the repository never gets staged.
#
# Stop form (S0-D4): the calling gate owns the stop and installs it as a trap
# before it calls this script:
#   trap 'kill $(cat PIDFILE)' EXIT
# The server runs with --save '' and --appendonly no, so a kill loses nothing.
# Never Docker.
set -u

pidfile="${1:?usage: redis-up.sh PIDFILE [LOGDIR]}"
logdir="${2:-$(dirname "$pidfile")}"
max_candidates=20
ping_tries=50
ping_sleep=0.1

port_listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

wait_pong() {
  local p="$1" pid="$2" i=0
  while [ "$i" -lt "$ping_tries" ]; do
    kill -0 "$pid" 2>/dev/null || return 1
    [ "$(redis-cli -p "$p" ping 2>/dev/null)" = "PONG" ] && return 0
    sleep "$ping_sleep"
    i=$((i + 1))
  done
  return 1
}

mkdir -p "$logdir" "$(dirname "$pidfile")" || {
  echo "REDIS-UP FAIL cannot create $logdir or $(dirname "$pidfile")"
  exit 1
}

attempt=0
while [ "$attempt" -lt "$max_candidates" ]; do
  attempt=$((attempt + 1))
  port=$((30000 + RANDOM % 20000))
  port_listening "$port" && continue
  log="$logdir/redis-$port.log"
  redis-server --port "$port" --bind 127.0.0.1 --save '' --appendonly no \
    --daemonize no >"$log" 2>&1 &
  pid=$!
  if wait_pong "$port" "$pid"; then
    printf '%s\n' "$pid" >"$pidfile"
    echo "REDIS-UP port=$port pid=$pid pidfile=$pidfile"
    exit 0
  fi
  kill "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null
done

echo "REDIS-UP FAIL no free loopback port after $max_candidates candidates"
exit 1
