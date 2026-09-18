# M1 Hash field/value writes

`hsetMany Reply g key pairs` takes a `Key Hash g` and a nonempty
`BulkPairs` value. Do-notation supplies the final
`Reply -> Script Reply g` continuation. The operation appends Script
tag 58. Single-field `hset` and all earlier tags remain stable.

```text
pairOne : Bytes -> Bytes -> BulkPairs
pairMore : Bytes -> Bytes -> BulkPairs -> BulkPairs
```

Each constructor takes a field and its value. The type rejects empty
requests, missing values, a `BulkArgs` list, incorrect key types and
incorrect tags before publishing artifacts.

One Redis HSET command creates or updates the Hash and returns the count
of new fields. Updating existing fields does not increase the count.
Repeated fields count once, with the last supplied value winning. These
semantics follow [Redis HSET](https://redis.io/docs/latest/commands/hset/).
Unmentioned fields and existing key expiry survive. Creating a missing
Hash leaves it persistent. WRONGTYPE preserves the complete value and expiry.

The operation uses write dispatch even if every supplied value is already
present. Empty and binary fields and values are supported. Node and Bash
can apply binary writes and return the count. Reading invalid UTF-8 data
later returns exit 4 without partial stdout; prior writes stay applied.

The Lua printer lowers constructor spines iteratively, including computed
fields, values and tails. The suite exercises 129-pair requests. General
compiler and Redis limits still apply.

```sh
dune build bin/tether.exe dev/store_run.exe dev/hset_many_tests.exe
./tether exec examples/ProfileBatch.tet --host node
./tether exec examples/ProfileBatch.tet --entry added --host bash
./tether exec examples/ProfileBatch.tet --entry retained --host luajit
sh dev/m1-hset-many.sh
```

The main entry prints
`["name","Alice","role","member","visits","9007199254740993"]`.
The other entries print `3`; `retained` keeps that reply after a second
Client invocation deletes the Hash. The suite also checks reply retention
across deletion in the same Script.

The ladder includes all earlier slices, 43 unit scenarios, nine artifact
pairs, 14 typed refusals, 23 store/twin cases, 52 live-host runs and nine
example executions. Six restored controls and 16 compiling mutations cover
counts, argument order, complete state, expiry, write classification and
the independent twin. Actual results are recorded in `dev/M1-BUILD-LOG.md`.
The shared store refactor updates the HSET-COUNT and HMGET INTERPRETER-ARGS
mutation anchors while preserving their existing assertions and counts.

The pinned preludes total 179 lines. Stage D's static walk uses 12 polls
after 64007 checker/erasure polls. Fuel 64013 leaves six walk polls and
must return `SH-BUDGET` without publishing output. All eight trusted-source
bounds and the 150 ms M0 timing bound remain unchanged.

Other Hash commands, List and Set bulk commands, ZSet support, remaining
examples, the Lean exporter and M1 performance milestones remain open.
