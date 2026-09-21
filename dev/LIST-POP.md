# M1 bulk List pops

`lpopMany` and `rpopMany` remove up to a count from the head or tail of a
typed `Key List g`. Their count is `Signed64`; both return `Reply` through
a continuation in `Script A g`. They append Script tags 69 and 70 without
changing existing constructor tags.

Each successful pop from an existing list returns an array of bulk replies
in removal order. Right pops therefore return the tail first. A count of
zero returns an empty array and leaves an existing list unchanged. A
missing or expired key returns `nil`, including at zero. Negative,
non-integer and overflowing counts return
`ERR value is out of range, must be positive`, before inspecting the key
type, as Redis 8.10.1 does. Canonical nonnegative counts on another Redis
type return WRONGTYPE.
Errors leave the value and its expiry unchanged.

Counts remain canonical decimal strings in Lua command arguments, so
`9223372036854775807` never passes through a Lua floating point conversion.
The OCaml store consumes at most the actual list length. The LuaJIT oracle
bounds the decimal count by that length before converting it. Popping the
last value removes the key and its expiry; a remaining list keeps its
existing expiry. Reply arrays own their captured values across later
commands and later Client invocations.

The command behavior follows Redis [LPOP](https://redis.io/docs/latest/commands/lpop/)
and [RPOP](https://redis.io/docs/latest/commands/rpop/) with their count
argument, available since Redis 6.2. The one-value `lpop` and `rpop`
commands retain their scalar reply shape. Bulk pops are writes and use
EVALSHA without `flags=no-writes`.

Run the example:

```sh
./tether exec examples/QueueDrain.tet --host node
./tether exec examples/QueueDrain.tet --entry newest --host bash
./tether exec examples/QueueDrain.tet --entry retained --host luajit
```

`main` and `retained` print `["welcome:alice","welcome:bob"]`, even after
`retained` deletes the queue. `remaining` prints `["welcome:carol"]`;
`newest` prints `["welcome:carol","welcome:bob"]`.

Run `sh dev/m1-list-pop.sh` for the inherited List move ladder and these
additional checks:

- 109 store and interpreter cases, including complete state and deadline
  comparisons, signed boundaries, malformed operands and error precedence.
- 19 emitted artifact pairs and 14 type or literal refusals with no output.
- 69 store and LuaJIT comparisons, covering empty and missing replies,
  duplicates, binary data, numeric-looking bytes and captured replies.
- 73 live Redis cases through Node/Wasm and Bash, with 146 host runs,
  four binary output refusals, two unhandled errors and four expiry cases.
- All four example entries through Node/Wasm, Bash and LuaJIT.
- 13 compiling semantic mutants with four restored positive controls.

The trusted limits remain store 200/200 and Lua 320/320. The existing
store helpers are packed within that same line budget; no bound is raised.
`SPEC.md` records all current counts. At that slice the two trusted
preludes contained 195 lines and were pinned in `dev/PRELUDES.sha256`.

At that slice the measured checker and erasure cost for `M0Spine.tet` was
89113 polls. The printer walk added 12. Stage D retained its zero-fuel
CHECK refusal and used fuel 89119 for the distinct `SH-BUDGET` refusal,
with no output. See `dev/STRING-BYTES.md` for the current prelude and fuel
counts.

Blocking pops, multi-key pops and other List bulk operations remain
outside this slice.

Validation on 2026-09-20: the new unit, integration and mutation checks
passed. The complete inherited ladder was stopped during List access
after its M0 timing gate failed at 808.934 ms against the 150 ms bound.
Its completed functional checks through Stage F passed. This is not a
completed or green full-ladder result.

Five interleaved warm samples measured the clean prior revision
`19c73d0` at 459.164 ms and this slice at 500.392 ms. Both exceed the
unchanged bound. These loaded-host measurements confirm that the timing
failure predates this slice; they do not isolate its performance delta.
See `dev/M1-BUILD-LOG.md` for captures and scoped regression results.

All four shared-code regression suites passed: List access, range,
removal and moves, including their units, integrations and mutations.
The final house, prelude-integrity and trusted-line checks also passed.
