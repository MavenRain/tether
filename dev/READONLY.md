# Read-only Redis dispatch

The second M1 slice executes scripts classified as `no-writes` with
`EVALSHA_RO`. An exact NOSCRIPT error retries once using `EVAL_RO`, with
the original Lua bytes and keys. Scripts that may write use `EVALSHA`
and `EVAL`. Each script retains its load state within the running Client, and
steady state still makes one request per invocation.

No syntax or reactor ABI changes are needed. The Lua printer already
walks all reachable definitions, case arms and closure captures to
derive `no-writes`. Bash selects the command suffix from that artifact
field. The Node host verifies the body's SHA-1, then recognizes the exact
canonical `#!lua flags=no-writes` first line, including its newline.
Other headers retain ordinary dispatch. Read-only mode belongs to each
body, so a Client can mix reads and writes and retain an earlier reply.

The local REST twin accepts `EVALSHA_RO` and `EVAL_RO` through the same
authenticated endpoint and independent decoder as the existing commands.
The read-only commands must be available on the target Redis server.
There is no downgrade on an unknown-command error, permission error,
network failure, or a failed fallback. Redis also enforces the script's
`no-writes` declaration. The tested local server is Redis 8.10.1.

```sh
dune build bin/tether.exe
./tether run examples/ReadOnly.tet
./tether exec examples/ReadOnly.tet --entry mixed --host node
./tether exec examples/ReadOnly.tet --entry mixed --host bash
sh dev/m1-readonly.sh
```

`main` reads a missing key and prints an empty line. `twice` reads it
twice using one SCRIPT LOAD. `mixed` increments, reads, increments again,
then prints the saved `1` while the stored value is `2`.

The full gate runs the M1 do-notation ladder, the host tests, artifact
integration, dispatch mutations and trusted-line counts. Every leg runs
even after another leg fails. The final verdict is `PASS M1-READONLY` or
`FAIL M1-READONLY` with a nonzero exit. Focused checks are:

```sh
node --test dev/readonly-host-tests.mjs
python3 -P dev/readonly-tests.py
python3 -P dev/readonly-mutations.py
```

The integration test emits all three example entries and checks canonical
Lua bytes in the actual Client Wasm and Bash artifacts. A temporary
loopback Redis denies ordinary EVAL and EVALSHA through its ACL while
both artifacts run the read-only entries. Twelve executions cover a
missing key and signed integer strings outside the exact JavaScript
integer range, compared with the independent store and LuaJIT. Stored
values and key existence are checked after each execution. Separate
checks flush Redis's script cache to exercise both hosts' EVAL_RO paths,
and confirm that Redis refuses a write from a no-writes body. Mixed
Clients verify per-script dispatch and captured replies after restoring
the ordinary evaluation permissions on that temporary server.

Mutation tests change Node command selection, Node fallback selection,
Bash command selection, and the REST allowlist in a disposable source
copy. The control and restored host and shell suites must pass. Each
mutant must compile and fail its named assertion, as recorded in
`dev/MUTATION-LOG.md`.

This slice leaves the pinned foundation, preludes and line bounds intact.
It does not complete the wider M1 command surface, application examples,
Lean exporter, or M1 performance and traversal gates. Live Upstash remains
M4 work.
