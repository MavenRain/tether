# Stage F driver and compiled Client

Build `dune build bin/tether.exe`, then use the repository's `./tether`
launcher from any working directory. Python owns filesystem and process
IO; `bin/tether.ml` owns checking, erasure, both printers and interpretation.
Source paths are relative to the caller's directory. `--root DIR` sets
the module source root and otherwise defaults to the source file's parent.

| Command | Behavior |
| --- | --- |
| `check FILE [--passes]` | Check modules; exit 1 on a check error. |
| `emit FILE -o DIR [--entry NAME]` | Emit to a fresh directory; exit 2 on failure. |
| `run FILE [--entry NAME]` | Interpret from an empty store and print the reply. |
| `exec FILE --host node\|bash\|luajit` | Run one host from an empty store and compare its stdout with the interpreter; exit 3 on disagreement. |
| `axioms FILE` | Print actual declared axiom names, one per line. The counter has none. |
| `spec-count` | Build the pinned counter and print the R0 census. |
| `bench` | Print the M0 timing and fixed-cost measurements. |

Runtime errors use exit 4. Each source command accepts `--fuel` and
`--entry`; check and axioms inspect the whole module. `exec` owns temporary
Redis and REST processes, authenticates to its REST twin, checks that Redis
readiness belongs to its child PID, and stops both children on failure as
well as success. It never connects to a pre-existing user's database.

An emitted directory contains `prog.wasm`, executable `prog.sh`, canonical
`body-N.lua` files, `scripts.json` and `client.json`. Wasm executes its own
compiled state machine. Neither JSON sidecar is needed to execute Wasm or
Bash. To run already emitted Wasm against a chosen local Redis server:

```sh
node runtime/redis-host.mjs .gatework/counter-client/prog.wasm 6379
```

The Client printer shares Bash's checked straight-line plan and its named
`SH-FIRST-ORDER` refusal. It supports repeated invocations, a saved earlier
reply, and explicit Client faults. Higher-order application, partial
application, inline scripts, constructed terminal replies and
reply-dependent branching retain their existing emission refusal.
The interpreter remains more general than this emission subset.

The generated reactor is checked over the carried prelude. Lua payloads
occupy typed Bytes slots, lowered directly to the inherited erased Bytes
constructors in chunks of at most 64 bytes. This avoids repeated
elaboration and deeply nested encoder work. A reference-lowering test
compares emitted bytes with ordinary checked byte literals for all 256
values, empty input and repeated binary data. The byte lowering is included
in the existing Lua trusted-line bound; Client control is included in the
existing shell printer bound. The driver, the command host and the local
process owner under `bin/` are counted by a new `bin` group with a bound of
450 lines, so a new implementation file there cannot escape the census. No
ruled bound and no vendored source changed.

Request code 10 passes `[sha1, ...keys]` and the Lua body to Redis. Status 0
resumes with a result envelope; status 1 ends the Client with exit 4.
Code 11 asks the host to format the selected result envelope with the same
exact text conventions as Bash. The existing code 6 raw-byte output remains
available. The host validates the envelope and safe reply domain before
writing it. Synchronous Wasm resource exhaustion remains residual.

`sh dev/stage-f.sh` runs the inherited A through E ladder, builds the
driver, tests the executable artifacts, checks PASSES, measures the timing
and ratios, and checks all eight trusted-line bounds. `LUA-SAME` executes
the Bash assignments and walks actual Wasm requests, comparing bodies,
SHA-1 values, keys, invocation order and the selected reply. It parses the
shell call block after the bodies block, so the `load` and `invoke` SHA-1
arguments, the octal key literals and the call order are compared with
`scripts.json` and the Client plan, and they enter the printed digest.
An array reply parity control compares the jq text, the Node host text and
the store text on fixtures holding the DEL byte. It checks all
emitted scripts and includes failure-only Clients. Eleven local three-host
cases exercise the counter, saved replies, both Int64 endpoints, values
past 2^53, missing keys, BOM, NUL and trailing newlines. The driver suite
also checks failure exit codes, first-order refusals and disagreement exit 3.

The Stage F mutations change one Lua byte inside Bash, change one octal key
byte in the shell call block and add checked definitions to the spine. The
added definitions start at 2,000 and double until the measured median
crosses the ruled 150 ms bound on the machine under test, and the crossing
count is printed. They must fail `LUA-SAME`, `LUA-SAME` and `M0-TIME`,
respectively. The body is restored and rechecked. The overloaded source
and all emitted artifacts live in temporary directories. A separate
boundary control rejects exactly 150 ms and accepts 149 ms; synthetic
samples never serve as the production M0 timing measurement.

Measurement uses `dev/m0-bench.sh`; the byte-identical inherited
`dev/bench.sh` stays frozen for Stage 0 denominators and CARRY. One warm-up
precedes five measured compilations. The timer starts at the compiler's
first source request and ends after both artifacts and their sidecars are
written and closed. Compiler and Python startup, wasm-opt, SCRIPT LOAD
and host execution are outside this interval. Every sample uses a fresh
compiler process and output directory, with no compiled-prelude or module
cache; operating-system file caches are not flushed.

`dev/ratio.sh` measures the same compile scope and prints ratios to all
three frozen denominator values. It also measures a fresh TinyCC spine and
empty translation unit, five samples each, within a 60-second window of
the compiler samples. This is one program, with source-line normalization,
and is informational. It does not claim parity across the four C programs
in the frozen denominator corpus. `FIXED-MS` compares a minimal failing
Client with the same source plus 100 definitions. Noise can make its
incremental estimate negative; no timing is clamped or gated on that estimate.

`--passes` observes reservation, rewriting and elaboration entry for each
surface declaration name. Its `class=surface-declaration` counters exclude
kernel recursion and prelude work. They are informational at M0. Full
kernel traversal instrumentation requires later work without changing
the pinned kernel in this stage.

The build log records measured gate results. M0-EXIT additionally requires
the user's Stage F commit, a green ladder on that committed tree and the
user's ratification. Staging this implementation does not supply that stamp.
