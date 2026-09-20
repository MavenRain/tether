# M1 Hash field selection

`hmget Reply g key fields` accepts a `Key Hash g` and a nonempty field
list. Its final `Reply -> Script Reply g` continuation is supplied by
do-notation. The Script constructor appends tag 52; existing tags stay fixed.

```text
bulkOne : Bytes -> BulkArgs
bulkMore : Bytes -> BulkArgs -> BulkArgs
```

`bulkMore b"role" (bulkMore b"missing" (bulkOne b"name"))` requests
three fields. Each position contains a bulk reply for an existing field
or nil for a missing field. A missing Hash produces one nil per request.
Order and duplicate fields are preserved. An empty bulk value stays
distinct from nil. The type excludes empty requests, and Hash type and
tag indices are checked before artifact publication.

These semantics follow [Redis HMGET](https://redis.io/docs/latest/commands/hmget/).
Wrong key types produce the standard WRONGTYPE reply. Reads leave the
Hash, its expiry and unrelated keys unchanged. Replies retained across a
later delete remain snapshots. HMGET-only scripts carry `no-writes` and
use the existing `EVALSHA_RO` and `EVAL_RO` dispatch.

The store and LuaJIT twin handle all byte values. Live Node and Bash
hosts retain their existing UTF-8 reply boundary: invalid UTF-8 values
produce exit 4 without partial stdout. Binary field names work because
they remain inside the emitted Lua body. Array nils become JSON null.

The Lua printer flattens syntactic `bulkMore` chains and reconstructs
them iteratively. This avoids Redis Lua's expression nesting limit for
large requests, including the 129-field integration case. Computed heads
and tails keep their normal expression semantics. General compiler,
Redis script and host resource limits still apply.

```sh
dune build bin/tether.exe dev/store_run.exe dev/hmget_tests.exe
./tether exec examples/ProfileFields.tet --host node
./tether exec examples/ProfileFields.tet --entry retained --host bash
sh dev/m1-hmget.sh
```

Both example entries print `["member",null,"Alice","member"]`.
The retained entry deletes the Hash before returning the earlier reply.

The validation ladder includes the conditional-expiry ladder, 26 unit
scenarios, ten emitted artifact pairs, ten typed refusals, 18 store/twin
cases, 42 live-host runs and six example executions. The live cases
check complete values and expiry deadlines, read-only ACLs, all five
wrong key types, binary fields and UTF-8 refusal. Six restored controls
and 16 compiling mutations cover argument order, nils, duplicates, state,
read-only flags and the independent twin.

At the HMGET slice, the prelude had 169 lines across both pinned files.
The Stage D static walk used 12 polls after 53323 checker/erasure polls;
fuel 53329 left six walk polls and returned `SH-BUDGET`. See
`dev/LIST-REMOVE.md` for the current prelude and fuel counts.
All eight trusted-source bounds and the 150 ms M0 timing bound are
unchanged. Actual gate results are recorded in `dev/M1-BUILD-LOG.md`.
Other Hash and List bulk commands, ZSet support, remaining examples,
the Lean exporter and the M1 performance milestones remain open.
