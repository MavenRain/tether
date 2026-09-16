# M1 expiry and persistence

The Script constructors below share a key's erased Redis type and tag:

| Constructor | Arguments after `Reply` | Script tag |
| --- | --- | --- |
| `expire` | `t g key duration` | 39 |
| `pexpire` | `t g key duration` | 40 |
| `ttl` | `t g key` | 41 |
| `pttl` | `t g key` | 42 |
| `persist` | `t g key` | 43 |

Each has a final `Reply -> Script Reply g` continuation, supplied by
do-notation. The key has type `Key t g`; durations have type `Signed64`.
All seven admitted key types, including both String encodings, are covered.
Wrong key types, tags and duration types fail before artifact publication.

EXPIRE uses seconds and PEXPIRE uses milliseconds. A successful expiry
change returns integer `1`; a missing key returns `0`. A nonpositive
duration deletes an existing key. Seconds conversion and absolute deadline
overflow are checked before looking up the key. These semantics follow
[EXPIRE](https://redis.io/docs/latest/commands/expire/) and
[PEXPIRE](https://redis.io/docs/latest/commands/pexpire/).

TTL and PTTL return the remaining lifetime in seconds or milliseconds.
The missing-key result is `-2`; a persistent key returns `-1`, following
[TTL](https://redis.io/docs/latest/commands/ttl/) and
[PTTL](https://redis.io/docs/latest/commands/pttl/). Seconds are rounded to
the nearest second, with half seconds rounded up. PERSIST removes the
deadline and returns `1` when it changed a key, otherwise `0`, following
[PERSIST](https://redis.io/docs/latest/commands/persist/).

TTL and PTTL are read-only and select EVALSHA_RO with EVAL_RO fallback.
Expiry changes and PERSIST select EVALSHA with EVAL fallback. Both artifacts
declare the key once and carry identical canonical Lua.

## Exact replies

Durations cross the Redis boundary as canonical signed decimal strings.
Redis's Lua interface returns expiry replies as numbers. The emitted body
therefore rejects replies at or above `9007199254740992`, replies below the
`-2` sentinel, nonintegers and reply shapes that are not numbers with
`err b"ERR expiry reply is outside exact integer range"`. One message covers
all four conditions. The largest supported positive reply is
`9007199254740991` and the smallest is `-2`. A larger
deadline can still be installed when Redis accepts it; a subsequent PTTL
may return the explicit error. No rounded value is converted to a decimal
reply. The interpreter enforces the upper limit only, because it derives
each lifetime from its own deadline map and never reads a host reply.

Errors are catchable Script replies. An uncaught error stops the Client
before its next invocation. The mutation preceding a reply-range error
remains applied, matching Redis's script behavior.

## Store clocks and deadlines

The persistent store contains values, millisecond deadlines and an explicit
nonnegative millisecond clock. `Store.empty` starts at zero.
`Store.advance milliseconds store` returns a new store, rejects negative
steps and overflow, and removes values whose deadlines are earlier than
the new clock. At the exact deadline PTTL returns `0`, matching the
[Redis 8.10.1 lookup rule](https://github.com/redis/redis/blob/8.10.1/src/db.c#L2720-L2728).
Setting a zero duration still deletes immediately. Old store snapshots
remain unchanged. `tether run` keeps
this logical clock fixed while executing a Client; it does not simulate
wall-clock time between invocations.

The independent LuaJIT twin uses decimal-string clock arithmetic.
Its fixture configuration accepts `now`, `deadlines` and per-invocation
`advance` values. Normal LuaJIT execution starts at zero with no clock
steps. Live Redis hosts use the server's clock. Clock-controlled tests
check elapsed milliseconds, the exact deadline and expiry one millisecond
later without sleeping.
Deadline overflow depends on the absolute clock value. For extreme
durations near the signed 64-bit limit, the zero-clock model can admit a
duration that a live Redis server rejects.

INCR, Hash, Set and List edits preserve deadlines while their keys survive.
SMOVE preserves both existing deadlines; a newly created destination is
persistent. SET and the Set store commands clear destination deadlines.
Deleting a key or its last collection element removes its deadline.
PERSIST clears only the deadline. Failed mutations keep both value and
deadline unchanged.

## Validation and scope

Run `sh dev/m1-ttl.sh` with the toolchain described in `dev/TOOLCHAIN.md`.
The ladder includes `dev/m1-set-move.sh`, 146 store unit checks, 35 expiry
scenarios on 34 interpreter and 35 LuaJIT oracles, three clock steps,
five atomic refusals: three typed and two literal-form, 70 live Wasm/Bash
executions, the example on three hosts, and 13 mutation checks with five
restored controls. The store scenario runner skips the uncaught-error case;
that path is tested in LuaJIT and on both live hosts. The LuaJIT fixtures
treat unsupported ZSet and Stream seeds as opaque values because these
commands inspect only existence and expiry metadata.

The enlarged prelude consumes 37788 checker/erasure polls for M0Spine,
followed by the unchanged 12-poll static walk. Stage D gives that walk
six polls at fuel 37794 and requires `SH-BUDGET`; its zero-fuel checker
refusal remains in place. SPEC records the current prelude count.
Trusted bounds remain unchanged: Lua 320/320,
store 200/200, and the other six measured bounds also retain their limits.

`examples/SessionLease.tet` creates a five-minute String lease and returns
its lifetime. Conditional expiry options, absolute expiry commands,
atomic SET-with-expiry options, the full session-store example and the
remaining M1 milestones are still pending.
