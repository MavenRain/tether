# M1 Set bulk changes

`saddMany Reply g key members` and `sremMany Reply g key members` accept
a `Key Set g` and a nonempty `BulkArgs` list. Their final
`Reply -> Script Reply g` continuation is supplied by do-notation.
They append Script tags 55 and 56. The single-member `sadd` and `srem`
signatures and all earlier tags remain stable.

```text
bulkOne : Bytes -> BulkArgs
bulkMore : Bytes -> BulkArgs -> BulkArgs
```

Each operation issues one Redis command and returns an integer count of
distinct members added or removed. Duplicate arguments contribute at most
one to that count. Existing members do not increase the `saddMany` count;
missing members do not increase the `sremMany` count. These semantics
follow [Redis SADD](https://redis.io/docs/latest/commands/sadd/) and
[Redis SREM](https://redis.io/docs/latest/commands/srem/).

A missing key becomes a persistent Set on addition. Removing members
from a missing key returns zero and leaves it absent. Removing the last
member deletes the key and its expiry. Other changes preserve its expiry
and unrelated keys. Wrong key types return WRONGTYPE and preserve the
complete value and expiry. Both operations are writes, including no-op
requests, and use EVALSHA/EVAL dispatch.

Empty and binary member values are supported. Live Node and Bash hosts
can change binary members and return the integer count. A later read of
invalid UTF-8 members returns exit 4 without partial stdout at the existing
reply boundary. The preceding Set change remains applied.

The type excludes empty requests and rejects incorrect key types, tags
and member argument shapes before publishing artifacts. Iterative
`BulkArgs` lowering supports the 129-member host cases and computed heads
and tails. General compiler and Redis resource limits still apply.

```sh
dune build bin/tether.exe dev/store_run.exe dev/set_bulk_tests.exe
./tether exec examples/TeamBatch.tet --host node
./tether exec examples/TeamBatch.tet --entry remaining --host bash
./tether exec examples/TeamBatch.tet --entry retained --host luajit
sh dev/m1-set-bulk.sh
```

The entries print `["alice","bob","carol"]`, `["bob"]` and `2`, respectively.
The retained entry keeps the removal reply after deleting the Set.

The ladder includes the List bulk ladder, 44 unit scenarios, 14 artifact
pairs, 20 typed refusals, 28 store/twin cases, 68 live-host runs and nine
example executions. Six restored controls and 16 compiling mutations
cover distinct counts, complete state, expiry, deletion, argument lowering,
write classification and the independent twin.

At the Set bulk slice, the two pinned preludes totaled 173 lines.
Stage D's static walk used 12 polls after 60327 checker/erasure polls.
Fuel 60333 left six walk polls and returned `SH-BUDGET` without publishing
output. See `dev/LIST-REMOVE.md` for the current prelude and fuel counts.
All eight trusted-source bounds and the 150 ms M0 timing bound are
unchanged.
The integer reply type checks remain defensive: Redis and the twin return
a number or error for these commands, so their malformed-type diagnostic
branches are not exercised by the host or mutation cases.

Actual validation results are recorded in `dev/M1-BUILD-LOG.md`. Other
Hash, List and Set bulk commands, ZSet support, remaining examples, the
Lean exporter and M1 performance milestones remain open.
