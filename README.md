# tether

tether is a small language for Redis scripts.  A tether program compiles to two artifacts: `prog.wasm` and `prog.sh`.  Both artifacts share the same Lua bodies.

## Status

M1 now supports bulk List pops with `lpopMany` and `rpopMany`. Each removes
up to a signed 64-bit count and returns the removed values in pop order.
Run `./tether exec examples/QueueDrain.tet --host node` to drain two jobs
and print `["welcome:alice","welcome:bob"]`. Its `retained` entry keeps
that reply after deleting the queue. See `dev/LIST-POP.md`; run
`sh dev/m1-list-pop.sh` for validation.

M1 now supports atomic List moves with `lmove` and typed `listLeft` and
`listRight` endpoints. Moves transfer a job between queues or rotate a
single queue while preserving existing expiries.
Run `./tether exec examples/QueueTransfer.tet --host node` to move a job
into a processing queue and print `welcome:alice`. Its `retained` entry
keeps that reply after deleting the processing queue; `rotated` prints
`["welcome:bob","welcome:alice"]`. See `dev/LIST-MOVE.md`; run
`sh dev/m1-list-move.sh` for validation.

M1 now supports insertion around List pivots with `linsertBefore` and
`linsertAfter`. Each command uses the first matching pivot and returns
the new length, `0` for a missing key, or `-1` for a missing pivot.
Run `./tether exec examples/QueueInsert.tet --host node` to insert a
priority job before another job and an audit job after it. Its `length`
and `missingPivot` entries return `4` and `-1`. See `dev/LIST-INSERT.md`;
run `sh dev/m1-list-insert.sh` for validation.

M1 now supports typed List removal with `lrem`. Positive and negative
counts remove matching values from the head and tail; zero removes all
matches. `./tether exec examples/QueueCleanup.tet --host node` removes
cancelled jobs and prints `["welcome:alice","welcome:bob"]`. Its `removed`
and `retained` entries return `2`, including after deleting the queue.
See `dev/LIST-REMOVE.md`; run `sh dev/m1-list-remove.sh` for validation.

M1 now supports conditional List pushes with `lpushx`, `rpushx`,
`lpushxMany` and `rpushxMany`. `./tether exec examples/ActiveQueue.tet --host node`
appends jobs to an open queue and prints `["open","welcome:alice","welcome:bob"]`.
Its `missing` entry returns `0` without creating a queue. See
`dev/LIST-CONDITIONAL.md`; run `sh dev/m1-list-conditional.sh` for validation.

M1 now supports conditional Hash writes with `hsetnx` and byte lengths
with `hstrlen`. `./tether exec examples/ProfileDefaults.tet --host node`
initializes missing fields without replacing existing values, prints
`["name","Alice","role","member"]`, and exposes the stored name's length
through its `length` entry.
See `dev/HASH-CONDITIONAL.md`; run `sh dev/m1-hash-conditional.sh` for validation.

M1 now supports variadic Hash writes with `hsetMany`. A nonempty
`BulkPairs` value keeps every field paired with its value.
`./tether exec examples/ProfileBatch.tet --host node` stores a profile in
one command and prints
`["name","Alice","role","member","visits","9007199254740993"]`. The
`added` and `retained` entries return the distinct new-field count `3`,
and `retained` keeps that count after a later invocation deletes the Hash.
See `dev/HSET-MANY.md`; run `sh dev/m1-hset-many.sh` for validation.

M1 now supports variadic Hash deletion with `hdelMany`.
`./tether exec examples/ProfileCleanup.tet --host node` removes stale
profile fields and prints `["name","Alice"]`. The `removed` and `retained`
entries return the distinct deletion count, including after deleting the
Hash. See `dev/HDEL-MANY.md`; run `sh dev/m1-hdel-many.sh` for validation.

M1 now supports variadic Set changes with `saddMany` and `sremMany`.
`./tether exec examples/TeamBatch.tet --host node` enrolls three distinct
members and prints `["alice","bob","carol"]`. The `remaining` entry removes
Alice and Carol, and `retained` keeps the removal count after deleting
the Set. See `dev/SET-BULK.md`; run `sh dev/m1-set-bulk.sh` for validation.

M1 now supports variadic List pushes with `lpushMany` and `rpushMany`.
`./tether exec examples/QueueBatch.tet --host node` enqueues three jobs
in one command and prints `["welcome:alice","welcome:bob","welcome:carol"]`.
The `priority` entry prepends urgent jobs, and `retained` keeps the returned
count after deleting the queue. See `dev/LIST-BULK.md`; run
`sh dev/m1-list-bulk.sh` for validation.

M1 now supports variadic HMGET on Hash keys. A typed nonempty field list
preserves request order, duplicates and nil replies for missing fields.
`./tether exec examples/ProfileFields.tet --host node` prints
`["member",null,"Alice","member"]`; `retained` keeps that reply after
deleting the Hash. See `dev/HMGET.md`; run `sh dev/m1-hmget.sh` for validation.

M1 now supports typed NX, XX, GT and LT conditions on relative and
absolute expiry. `./tether exec examples/SessionRenewal.tet --host node`
extends a session lease to ten minutes, rejects a shorter renewal and
prints `600`. See `dev/CONDITIONAL-EXPIRY.md`; run
`sh dev/m1-conditional-expiry.sh` for its full validation ladder.

M1 now supports typed EXPIREAT, PEXPIREAT, EXPIRETIME and PEXPIRETIME
on all key types. `./tether exec examples/SessionDeadline.tet --host node`
sets an absolute session deadline and prints `4102444800`.
See `dev/ABSOLUTE-EXPIRY.md`; run `sh dev/m1-absolute-expiry.sh` for
its full validation ladder.

M1 now supports typed EXPIRE, PEXPIRE, TTL, PTTL and PERSIST on all key
types. Expiry replies are checked for exact integer representation.
`./tether exec examples/SessionLease.tet --host node` creates a five-minute
lease and prints `300`. See `dev/TTL.md`; run `sh dev/m1-ttl.sh` for its
full validation ladder.

M1 now supports typed SMOVE between two Set keys. Transfers preserve
existing expiries and return whether the member was present in the source.
`./tether exec examples/TeamTransfer.tet --host node` prints
`["alice","carol"]`; `retained` keeps the transfer reply after deleting
the destination, and `unchanged` moves within one Set. See
`dev/SET-MOVE.md` for semantics and validation.

M1 now supports typed SUNIONSTORE, SINTERSTORE and SDIFFSTORE with a
destination and two Set inputs. `./tether exec examples/TeamCache.tet --host node`
prints `["alice","bob","carol"]` after caching a union. `exclusive`
replaces an input with its difference, and `retained` keeps the returned
count after deleting the destination. See `dev/SET-STORE.md` for semantics
and validation.

M1 now supports typed SUNION, SINTER and SDIFF for two Set keys, with
unique members sorted by bytes. `./tether exec examples/TeamAccess.tet --host node`
prints `["alice","bob","carol"]`; `common`, `exclusive` and `retained`
demonstrate intersection, difference and retained replies. See
`dev/SET-ALGEBRA.md` for semantics and validation.

M1 now supports typed HKEYS and HVALS on Hash keys. Both return arrays
sorted by bytes, and HVALS retains duplicate values.
`./tether exec examples/HashCatalog.tet --host node` prints
`["name","plan","role"]`. The `retained` entry returns
`["Alice","member","member"]` after deleting the Hash. See
`dev/HASH-PROJECTIONS.md` for ordering and validation.

M1 now supports typed HGETALL on Hash keys, with field/value pairs sorted
by field bytes. `./tether exec examples/HashSnapshot.tet --host node`
prints `["name","Alice","visits","9007199254740993"]`. See
`dev/HASH-ENTRIES.md` for ordering, retained replies and validation.

M1 now supports typed SMEMBERS on Set keys, with members sorted by bytes.
`./tether exec examples/TeamRoster.tet --host node` prints
`["alice","bob"]`. See `dev/SET-MEMBERS.md` for ordering and validation.

M1 now supports typed LRANGE on List keys, returning ordered arrays with
exact signed 64-bit bounds. `./tether exec examples/QueuePreview.tet --host node`
prints `["welcome:alice","welcome:bob"]`. The `retained` entry keeps that
preview across a later trim. See `dev/LIST-RANGE.md` for semantics and validation.

M1 now supports typed LINDEX, LSET and LTRIM on List keys, with exact
signed 64-bit indices. `./tether exec examples/RecentJobs.tet --host node`
updates a queued job, retains the two newest jobs and prints
`welcome:bob`. See `dev/LIST-ACCESS.md` for semantics and validation.

M1 now supports typed LPUSH, RPUSH, LPOP, RPOP and LLEN on List keys.
`./tether exec examples/JobQueue.tet --host node` drains a FIFO queue
and prints its first job, `welcome:alice`. See `dev/LISTS.md` for types,
binary reply limits and validation.

M1 now supports typed SADD, SREM, SISMEMBER and SCARD on Set keys.
`./tether exec examples/Sets.tet --host node` enrolls two distinct members
and prints `2`. See `dev/SETS.md` for types, binary members and validation.

M1 now supports typed HSET, HGET, HDEL, HEXISTS, HLEN and HINCRBY on
Hash keys. `./tether exec examples/Hashes.tet --host node` demonstrates
field updates and exact arithmetic beyond 2^53. See `dev/HASHES.md` for
command types, binary reply limits and validation.

M1 now supports typed SET, INCRBY, DECR, DEL and EXISTS alongside INCR
and GET. `./tether exec examples/Strings.tet --host node` demonstrates
exact arithmetic beyond 2^53. See `dev/STRINGS.md` for command types,
examples and validation.

M1 adds `do { reply <- command; finalTerm }` syntax for Script and Client
continuations, plus read-only Redis dispatch. Scripts classified as
`no-writes` use `EVALSHA_RO` and fall back to `EVAL_RO` on NOSCRIPT.
Try `./tether exec examples/ReadOnly.tet --host node` after building the
driver, or select `--entry mixed` to combine reads and writes. See
`dev/DO-NOTATION.md` and `dev/READONLY.md` for syntax and checks.

The Stage F driver emits an executable Client `prog.wasm` and `prog.sh`
with the same canonical Lua bodies. Both run against local Redis hosts
and agree with LuaJIT and the independent store interpreter. The final
M0 timing gate is measured separately from functional correctness; see
`dev/STAGE-F.md` and the latest entry in `dev/M0-BUILD-LOG.md`.

```sh
dune build bin/tether.exe
./tether check examples/M0Spine.tet --passes
./tether emit examples/M0Spine.tet -o .gatework/counter-client
./tether run examples/M0Spine.tet
./tether exec examples/M0Spine.tet --host node
./tether exec examples/M0Spine.tet --host bash
./tether exec examples/M0Spine.tet --host luajit
sh dev/stage-f.sh
```

`exec` starts and stops its own temporary loopback Redis server and REST
twin, then compares the chosen host's stdout with the empty-store
interpreter. The counter commands above print `1`. Emit requires a fresh output directory.

```sh
dune build dev/surface_check.exe
python3 -P dev/check.py --root examples M0Spine.tet
sh dev/stage-b.sh
dune build dev/lua_emit.exe dev/sha1_probe.exe
python3 -P dev/emit-lua.py --root examples M0Spine.tet -o .gatework/counter
sh dev/stage-c.sh
dune build dev/sh_emit.exe
python3 -P dev/emit-sh.py --root examples M0Spine.tet -o .gatework/bash-counter
sh dev/stage-d.sh
sh dev/stage-e.sh
```

See `dev/STAGE-B.md` for module syntax, schemas, erased constructors,
validation scope and the additional `panicscan` gate dependency.
See `dev/STAGE-C.md` for Lua emission, artifact inspection and validation.
See `dev/STAGE-D.md` for Bash emission, reply formatting and current limits.
See `dev/STAGE-E.md` for local hosts, the store and integration validation.
See `dev/STAGE-F.md` for the driver, compiled Client and measurement scope.

## Files

- Source files end in `.tet`.
- A module name is dotted PascalCase.  A module name equals its path under the source root.  The module `Data.Reply` lives in `Data/Reply.tet`.

## Foundation

tether builds on kanon at pin 2c2e6e6, carried as `vendor/kanon` with zero
patches. See `SPEC.md` and `dev/PIN`. Stage 0's tool record and frozen spike
outputs remain under `dev/`.

Initialize the submodule, then run the foundation gates. The gates need Git,
Python 3.11 or newer for the `-P` flag, zsh, ripgrep, shasum, awk, wc, OCaml
5.2.1, Dune 3.24.2 and Zarith 1.14 on PATH:

```sh
git -c protocol.file.allow=always submodule update --init vendor/kanon
sh dev/stage-a.sh
python3 -P dev/stage-a-mutations.py
```

Run the three commands in this order. `sh dev/stage-a.sh` builds
`vendor/kanon/bin/kanon.exe`, and the mutation battery copies that
executable into every temporary tree. Without the build the battery stops
with a control failure.

The submodule URL is the ruled local `/Users/oobi/Documents/kanon` path.
After initialization, builds and gates use only `vendor/kanon`.
The development emitter writes `script.lua`, `body.wasm` and `script.json`.
The Bash emitter writes `prog.sh`, the Client schedule, keys and one
Lua/Wasm carrier pair per script. The Node integration runner executes
that schedule using the Wasm carriers and a loopback Redis server.
The `tether` command emits the full Client Wasm and Bash pair. The earlier
development emitters remain available for inspecting per-script carriers.

## License

MIT OR Apache-2.0.  See `LICENSE-MIT` and `LICENSE-APACHE`.
