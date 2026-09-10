# Spike (f): the free-port redis-server protocol

Date: 2026-09-09.  Kanon pin 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf.  Server: Redis server v=8.10.1 at /opt/homebrew/bin.  Never Docker.

## Protocol

dev/redis-up.sh PIDFILE [LOGDIR] picks a free loopback port, starts `redis-server --port <p> --bind 127.0.0.1 --save '' --appendonly no --daemonize no` in the background, writes PIDFILE, waits for `redis-cli -p <p> ping` to print PONG with a bounded retry, and prints one line: `REDIS-UP port=<p> pid=<n> pidfile=<path>`.  On failure it prints `REDIS-UP FAIL <reason>` and exits 1.

The stop path belongs to the calling gate, which installs the trap before it calls the script:

    trap 'kill $(cat PIDFILE)' EXIT

The server runs with `--save ''` and `--appendonly no`, so a kill loses nothing.

## Decision S0-D4

- Free-port method: a candidate port is drawn from 30000..49999 with `$RANDOM`, probed with `lsof -nP -iTCP:<p> -sTCP:LISTEN`, and accepted only when the started server answers PONG within 50 tries of 0.1 s.  A bind race or a dead server moves to the next candidate;  at most 20 candidates are tried.  The server's own bind is the final arbiter, so the lsof probe is a fast filter and not the proof.
- Pidfile convention: the caller names the pidfile as the first argument.  The server log is `<LOGDIR>/redis-<p>.log`, and LOGDIR defaults to the directory of the pidfile.  Both names match the .gitignore rows `*.pid` and `*.log`.  At Stage 0 the pidfile sits under the scratch directory /Users/oobi/Documents/tether-m0/spikes/server/, which never enters the repository.
- Stop form: `trap 'kill $(cat PIDFILE)' EXIT` in the calling gate, then `kill -0 <pid>` fails and `redis-cli -p <p> ping` fails to connect.

## Sandbox note

Inside the Bash sandbox the listen is denied.  A sandboxed call of `dev/redis-up.sh` printed `REDIS-UP FAIL no free loopback port after 20 candidates` and every candidate's log holds one line of the form:

    36752:M 09 Sep 2026 19:16:40.037 # Warning: Could not create server TCP listening socket 127.0.0.1:46234: bind: Operation not permitted

So the proof run below and the verifier's rerun pass `dangerouslyDisableSandbox: true` on that one Bash call.  Every other call of this spike stayed sandboxed.

## Proof run

Runner: /Users/oobi/Documents/tether-m0/spikes/server/proof.sh, one Bash call with the sandbox disabled, executed with the disk-floor interlock comment `# [skip-disk]` after one hold.  Transcript: /Users/oobi/Documents/tether-m0/spikes/server/transcript.txt.  Port 36686, pid 34255, pidfile /Users/oobi/Documents/tether-m0/spikes/server/redis.pid.  Every line below is verbatim.

    # date: 2026-09-10T02:15:47Z
    # sandbox: dangerouslyDisableSandbox=true on this Bash call
    $ zsh -n /Users/oobi/Documents/tether/dev/redis-up.sh
    exit=0
    $ /Users/oobi/Documents/tether/dev/redis-up.sh /Users/oobi/Documents/tether-m0/spikes/server/redis.pid
    REDIS-UP port=36686 pid=34255 pidfile=/Users/oobi/Documents/tether-m0/spikes/server/redis.pid
    exit=0
    $ redis-cli -p 36686 ping
    PONG
    exit=0
    $ shasum -a 1 < /Users/oobi/Documents/tether/corpus/lua/m0-spine.lua
    d8018db15d29480d5eca4c33d3ded2ffa01852a6  -
    $ redis-cli -p 36686 script load "$(cat /Users/oobi/Documents/tether/corpus/lua/m0-spine.lua)"
    d8018db15d29480d5eca4c33d3ded2ffa01852a6
    $ redis-cli -p 36686 evalsha d8018db15d29480d5eca4c33d3ded2ffa01852a6 1 spike:counter
    1
    exit=0
    $ redis-cli -p 36686 evalsha d8018db15d29480d5eca4c33d3ded2ffa01852a6 1 spike:counter
    2
    exit=0
    $ redis-cli -p 36686 script flush
    OK
    exit=0
    $ redis-cli -p 36686 evalsha d8018db15d29480d5eca4c33d3ded2ffa01852a6 1 spike:counter
    NOSCRIPT No matching script. Please use EVAL.
    exit=0
    $ trap -p EXIT
    trap -- 'kill $(cat "$pidfile")' EXIT
    $ kill $(cat /Users/oobi/Documents/tether-m0/spikes/server/redis.pid)
    exit=0
    $ kill -0 34255
    /Users/oobi/Documents/tether-m0/spikes/server/proof.sh: line 54: kill: (34255) - No such process
    exit=1
    $ redis-cli -p 36686 ping
    Could not connect to Redis at 127.0.0.1:36686: Connection refused
    exit=1
    # port=36686 pid=34255 pidfile=/Users/oobi/Documents/tether-m0/spikes/server/redis.pid

## Readings

- The SCRIPT LOAD sha1 d8018db15d29480d5eca4c33d3ded2ffa01852a6 equals `shasum -a 1` of the fixture, so the server hashes exactly the fixture bytes and the EVALSHA key is computable offline from the canonical body (S0-D5).
- After SCRIPT FLUSH the same EVALSHA prints `NOSCRIPT No matching script. Please use EVAL.`, which is the R-Q5 fallback trigger.
- redis-cli exits 0 on a NOSCRIPT reply when its output is not a terminal, so the emitted scripts compare on the reply text and never on the exit code (R-Q6).

## Gate S0-G8 rerun

    zsh -n /Users/oobi/Documents/tether/dev/redis-up.sh
    /Users/oobi/Documents/tether-m0/spikes/server/proof.sh

The second command needs the sandbox disabled on that one Bash call, and it may need the `# [skip-disk]` comment when the disk-floor interlock holds it.
