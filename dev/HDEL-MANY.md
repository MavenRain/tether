# M1 Hash field deletion

`hdelMany Reply g key fields` takes a `Key Hash g` and a nonempty
`BulkArgs` field list. Do-notation supplies the final
`Reply -> Script Reply g` continuation. The operation appends Script
tag 57. Single-field `hdel` and all earlier tags remain stable.

```text
bulkOne : Bytes -> BulkArgs
bulkMore : Bytes -> BulkArgs -> BulkArgs
```

One Redis HDEL command removes all requested fields and returns the
integer count of distinct fields removed. Duplicate and missing fields
do not increase the count. A missing Hash returns zero and stays absent.
Removing its final field deletes the key and expiry. A nonempty Hash
keeps its expiry, remaining fields and values. WRONGTYPE preserves the
complete value and expiry. These semantics follow
[Redis HDEL](https://redis.io/docs/latest/commands/hdel/).

The operation is a write, including no-op requests, so it uses EVALSHA/EVAL
dispatch. Empty and binary field names are supported. The Node and Bash
hosts can remove binary fields and return the integer count. A subsequent
read of invalid UTF-8 data returns exit 4 without partial stdout, while
the preceding deletion remains applied.

The type excludes empty requests and rejects incorrect key types, tags
and argument shapes before publishing artifacts. Computed heads and
tails use the existing iterative `BulkArgs` lowering. The validation
includes 129-field requests; general compiler and Redis limits apply.

```sh
dune build bin/tether.exe dev/store_run.exe dev/hdel_many_tests.exe
./tether exec examples/ProfileCleanup.tet --host node
./tether exec examples/ProfileCleanup.tet --entry removed --host bash
./tether exec examples/ProfileCleanup.tet --entry retained --host luajit
sh dev/m1-hdel-many.sh
```

These entries print `["name","Alice"]`, `2` and `2`, respectively.
The retained entry keeps the reply across a later Client invocation that
deletes the Hash. The suite also retains a reply across a deletion in the
same Script.

The ladder includes the Set bulk ladder, 36 unit scenarios, nine artifact
pairs, ten typed refusals, 21 store/twin cases, 48 live-host runs and nine
example executions. Five restored controls and 14 compiling mutations
cover distinct counts, complete state, expiry, deletion, argument lowering,
write classification and the independent twin.

At this slice's close, the two pinned preludes totaled 174 lines.
Stage D's static walk used 12 polls after 62148 checker/erasure polls.
Fuel 62154 left six walk polls and returned `SH-BUDGET` without
publishing output. See `dev/LIST-CONDITIONAL.md` for the current prelude and
fuel counts. All eight trusted-source bounds and the 150 ms M0 timing
bound remain unchanged.
The malformed integer reply diagnostic is defensive and has no mutation
claim; Redis and the twin return a number or error for HDEL.

Actual validation results are recorded in `dev/M1-BUILD-LOG.md`. Bulk
Hash writes are described in `dev/HSET-MANY.md`. Other List and Set bulk
commands, ZSet support, remaining
examples, the Lean exporter and M1 performance milestones remain open.
