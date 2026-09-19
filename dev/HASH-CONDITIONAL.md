# M1 conditional Hash writes and byte lengths

`hsetnx Reply g key field value` sets a field only if it is absent.
An existing field, including one holding an empty value, stays unchanged.
The reply is integer 1 for a new field and 0 for an existing one.
`hstrlen Reply g key field` returns the stored value's byte length, or
integer 0 for a missing key or field. Both operations require `Key Hash g`;
do-notation supplies their `Reply -> Script Reply g` continuation.
They append Script tags 59 and 60. Earlier tags retain their meanings.

The semantics follow [Redis HSETNX](https://redis.io/docs/latest/commands/hsetnx/)
and [Redis HSTRLEN](https://redis.io/docs/latest/commands/hstrlen/).
`hsetnx` emits a single atomic HSETNX command. It always uses write dispatch,
including when the field already exists. `hstrlen` is eligible for
`EVALSHA_RO`; a Script containing a later write uses write dispatch.

Both preserve existing key expiry and unrelated fields. Creating a missing
Hash leaves it persistent. A WRONGTYPE reply preserves the complete value
and expiry. Missing reads leave the key absent. Fields and values may be
empty or binary, including invalid UTF-8. Length counts bytes, so the
UTF-8 value `é🙂` has length 6. Its integer reply needs no text decoding of
the stored value. Captured replies survive subsequent deletion both inside
a Script and across Client invocations.

```sh
dune build bin/tether.exe dev/store_run.exe dev/hash_conditional_tests.exe
./tether exec examples/ProfileDefaults.tet --host node
./tether exec examples/ProfileDefaults.tet --entry length --host bash
./tether exec examples/ProfileDefaults.tet --entry retained --host luajit
sh dev/m1-hash-conditional.sh
```

The example initializes a profile's name and role, tries to replace the
name, and prints `["name","Alice","role","member"]`. `length` prints 5;
`retained` returns the first insertion's reply, 1.

The ladder includes all earlier slices and pins 32 unit scenarios,
13 artifact pairs, 15 typed refusals, 34 store/twin cases, 80 live-host
runs and nine example executions. Thirteen compiling mutations cover
conditional writes, reply counts, expiry, byte lengths, interpreter and
Lua dispatch, read-only classification and the independent twin. Three
restored controls confirm the clean implementation still passes.
Actual results are recorded in `dev/M1-BUILD-LOG.md`.

The pinned preludes total 181 lines. Stage D's static walk uses 12 polls
after 67862 checker/erasure polls. Fuel 67868 leaves six walk polls and
must return `SH-BUDGET` without publishing output. The checker zero-fuel
refusal, all eight trusted-source bounds and the 150 ms M0 timing bound
remain unchanged. The store shares HSET's update path with an `nx` guard;
the existing bulk-write mutation retains its type-check assertion.

Other Hash commands, List and Set bulk commands, ZSet support, remaining
examples, the Lean exporter and M1 performance milestones remain open.
