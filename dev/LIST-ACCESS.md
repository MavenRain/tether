# M1 List access

LINDEX, LSET and LTRIM add indexed reads, replacement and trimming to
the existing List commands. Every constructor takes erased result type
`A` and tag `g`, followed by the operands below and a
`Reply -> Script A g` continuation. Do-notation supplies that continuation.

| Constructor | Runtime operands | Successful reply |
| --- | --- | --- |
| `lindex` | `Key List g`, index `Signed64` | `bulk` element, or `nil` if missing or outside the list |
| `lset` | `Key List g`, index `Signed64`, replacement `Bytes` | `status` containing `OK` |
| `ltrim` | `Key List g`, start `Signed64`, inclusive stop `Signed64` | `status` containing `OK` |

Indices start at zero. Negative indices count from the tail, so `-1`
selects the last element. LINDEX preserves the list and distinguishes an
empty bulk value from nil. These semantics follow
[LINDEX](https://redis.io/docs/latest/commands/lindex/).

LSET preserves length and returns a typed error for a missing key
(`ERR no such key`) or an index outside an existing list
(`ERR index out of range`). A failed replacement leaves every element
unchanged. See [LSET](https://redis.io/docs/latest/commands/lset/).

LTRIM retains both endpoints, clips bounds to the available elements,
and deletes the key when the selected range is empty. A missing list
returns `OK` without creating a key. See
[LTRIM](https://redis.io/docs/latest/commands/ltrim/).

Indices use `int64 b"..."`, with the full signed 64-bit range, including
`-9223372036854775808` and `9223372036854775807`. The Lua printer passes
the decimal bytes to Redis without a numeric conversion. The store uses
Int64 arithmetic; normalizing a negative index adds the list length and
does not negate the minimum integer. The independent LuaJIT twin bounds
the decimal magnitude by the list length before converting it.

The surface refuses noncanonical and overflowing integer literals.
The store's defensive error paths also follow Redis's validation order:
LINDEX and LSET check key existence and type before parsing an index;
LTRIM parses both bounds before looking up the key. The unit suite
exercises those paths directly with erased terms. This order is visible
in Redis's [List implementation](https://github.com/redis/redis/blob/unstable/src/t_list.c).

All three operations return a typed `err` on a wrong Redis type. A Script
can inspect that reply; returning it from an invocation stops the Client.
LINDEX joins the read-only allowlist and uses EVALSHA_RO with EVAL_RO
fallback. LSET and LTRIM use write dispatch, including writes in a
reachable case arm that is not taken during a particular run.

Replacement bytes and stored values retain NUL, invalid UTF-8 and other
binary content. The store and LuaJIT can return arbitrary bytes. Existing
Node and REST text hosts reject invalid UTF-8 replies with exit 4 and no
stdout; UTF-8, NUL, BOM and trailing newlines survive. A read refusal
preserves the list. LSET can store invalid UTF-8 because its reply is `OK`.

```sh
dune build bin/tether.exe
./tether exec examples/RecentJobs.tet --host node
./tether exec examples/RecentJobs.tet --entry newest --host bash
./tether exec examples/RecentJobs.tet --entry newest --host luajit
sh dev/m1-list-access.sh
```

The default example prints `welcome:bob`; `newest` prints `retry:carol`.
Each run owns an empty temporary store. The example keeps two recent
jobs and demonstrates replacement and trimming. It has no durable
delivery, acknowledgement or retry protocol.

The constructors append tags 24 through 26 without changing older tags.
At the List access close, the two pinned preludes totaled 133 lines.
Shared operand and reply adapters in the interpreter preserve the
distinction between Bytes and Signed64 and convert store faults into
typed errors. Trusted counts at that close were Lua 318/320 and store
200/200. Every bound is unchanged.

The gate runs the complete List ladder, then requires 83 unit cases,
19 artifact pairs, 28 typed refusals with no published output, 49 store
and 49 LuaJIT comparisons, 98 live host runs, 38 runs with write EVAL
commands denied, two invalid UTF-8 refusals, six example runs, and twelve
compiled mutants killed at their intended assertions. Six controls
pass before and after mutation. A failed build skips dependent suites
and makes the aggregate fail, so stale executables cannot satisfy it.

`python3 -P dev/list-access-tests.py --offline` omits listeners;
`--static` checks artifacts, refusals and interpreter examples;
`--artifacts` emits the artifact pairs and checks write classification
only; `--probe ENTRY` runs a single artifact and its LuaJIT cases for
mutation controls. A run with a mode flag prints its mode in the
summary row. The build log records actual gate results and timing separately.
LRANGE replies are now implemented in `dev/LIST-RANGE.md`. Bulk List
operations, TTL, ZSet operations and the other remaining M1 work are
still listed in `SPEC.md`.
