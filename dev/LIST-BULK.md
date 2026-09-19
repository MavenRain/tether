# M1 List bulk pushes

`lpushMany Reply g key values` and `rpushMany Reply g key values` accept
a `Key List g` and a nonempty `BulkArgs` list. Their final
`Reply -> Script Reply g` continuation is supplied by do-notation.
They append Script tags 53 and 54. Existing tags and the single-value
`lpush` and `rpush` signatures stay fixed.

```text
bulkOne : Bytes -> BulkArgs
bulkMore : Bytes -> BulkArgs -> BulkArgs
```

Both commands return the resulting List length as an integer reply.
`lpushMany` inserts the arguments at the head in request order, so pushing
`a`, `b`, `c` before `old` produces `c`, `b`, `a`, `old`.
`rpushMany` appends them in request order, producing `old`, `a`, `b`, `c`.
Duplicates, empty values and all byte values are preserved. Each emitted
operation makes one Redis command call.

These semantics follow [Redis LPUSH](https://redis.io/docs/latest/commands/lpush/)
and [Redis RPUSH](https://redis.io/docs/latest/commands/rpush/).
A missing key becomes a persistent List. Existing expiries and unrelated
keys are preserved. Wrong key types return WRONGTYPE without changing
the value or its expiry. The type excludes an empty request and rejects
keys of another Redis type or tag before publishing artifacts.

Both operations are classified as writes, including one-value requests.
They use the existing EVALSHA/EVAL dispatch. The independent store and
LuaJIT twin support binary List contents. Live Node and Bash hosts can
push binary values and return the integer length. Reading invalid UTF-8
contents back still returns exit 4 without partial stdout at the existing
host reply boundary. The preceding push remains applied in that case.

The existing iterative `BulkArgs` lowering supports the 129-value host
cases without nested Lua expressions. Computed argument heads and tails
retain their expression semantics. General compiler and Redis resource
limits still apply.

```sh
dune build bin/tether.exe dev/store_run.exe dev/list_bulk_tests.exe
./tether exec examples/QueueBatch.tet --host node
./tether exec examples/QueueBatch.tet --entry priority --host bash
./tether exec examples/QueueBatch.tet --entry retained --host luajit
sh dev/m1-list-bulk.sh
```

The main entry prints `["welcome:alice","welcome:bob","welcome:carol"]`.
The priority entry prepends `retry:bob` and `retry:alice` in that order.
The retained entry returns `3` after deleting the List.

The ladder includes the HMGET ladder, 40 unit scenarios, 13 artifact
pairs, 20 typed refusals, 23 store/twin cases, 56 live-host runs and nine
example executions. Six restored controls and 16 compiling mutations
cover ordering, complete state, argument lowering, write classification
and the independent twin. Two lines of `print/lua.ml` are defence in depth
for tags 53 and 54: line 105 keeps the expiry message for tags 39 to 51,
and line 108 keeps the member-count message for tags 35 to 37. Redis
answers an integer for `LPUSH` and `RPUSH`, and the twin
`dev/lua-store.lua` answers a number or an error table that line 104
catches first. No host reaches these two lines, so no mutation covers
them.

At the List bulk push slice, the two pinned preludes totaled 171 lines.
Stage D's static walk used 12 polls, after 56769 checker/erasure polls.
Fuel 56775 left six walk polls and returned `SH-BUDGET` without publishing
output. See `dev/HASH-CONDITIONAL.md` for the current prelude and fuel counts.
The eight trusted-source bounds and the 150 ms M0 timing bound are unchanged.
Actual gate results are recorded in `dev/M1-BUILD-LOG.md`. Other Hash,
List and Set bulk commands, ZSet support, remaining examples, the Lean
exporter and M1 performance milestones remain open.
