# M1 Set commands

The Set slice adds SADD, SREM, SISMEMBER and SCARD. The example enrolls
Alice and Bob, repeats Alice's enrollment, reads membership in a separate
read-only invocation, and removes the members.

```sh
dune build bin/tether.exe
./tether exec examples/Sets.tet --host node
./tether exec examples/Sets.tet --host bash
./tether exec examples/Sets.tet --host luajit
./tether exec examples/Sets.tet --entry duplicate --host node
./tether exec examples/Sets.tet --entry present --host bash
./tether exec examples/Sets.tet --entry deleted --host node
```

The default entry prints `2`, `duplicate` prints `0`, `present` prints
`1`, and `deleted` prints `0`. Every `exec` owns an empty temporary store.

Every constructor starts with erased result type `A` and tag `g`, and
ends with a `Reply -> Script A g` continuation supplied by do-notation.

| Constructor | Runtime operands | Successful reply |
| --- | --- | --- |
| `sadd` | `Key Set g`, member `Bytes` | `int` 1 if added, 0 if already present |
| `srem` | `Key Set g`, member `Bytes` | `int` 1 if removed, 0 if absent |
| `sismember` | `Key Set g`, member `Bytes` | `int` 1 if present, 0 if absent |
| `scard` | `Key Set g` | `int` number of distinct members |

SADD creates a missing set and preserves other members. SREM deletes
the key after removing its last member. Missing keys give zero for
SREM, SISMEMBER and SCARD. Every command returns a typed `err` on a
key holding a different Redis type and preserves the store on failure.
These semantics follow the Redis contracts for
[SADD](https://redis.io/docs/latest/commands/sadd/),
[SREM](https://redis.io/docs/latest/commands/srem/),
[SISMEMBER](https://redis.io/docs/latest/commands/sismember/) and
[SCARD](https://redis.io/docs/latest/commands/scard/).

Members use exact byte identity. Empty members, NUL, non-UTF-8 octets,
quotes, backslashes and newlines are valid. `b"1"` and `b"01"` are
distinct members. Members stay inside the canonical Lua body, and all
four commands return integer replies, so binary members work through
both text hosts. The integers cross the artifact boundary as decimal
bulk strings using the existing count-reply path.

SISMEMBER and SCARD join the read-only allowlist, selecting EVALSHA_RO
and EVAL_RO. SADD and SREM require write-capable dispatch. The classifier
includes writes in reachable case arms even when that arm is not taken.
Scripts can inspect an `err`; returning it from an invocation stops the
Client. Schema checking refuses Set commands on other key types or tags.

This slice supports one member per SADD and SREM. Enumeration, set
algebra, random members, multi-member forms and TTL remain outside this
slice. The remaining M1 applications and performance gates are listed
in `SPEC.md`; this slice does not declare M1 complete.

The prelude appends four constructors, retaining existing tags. Its
checksum is updated in `dev/PRELUDES.sha256`; the two preludes total
125 lines. Trusted counts are Lua 310/320 and store 185/200. All other
counts and every bound are unchanged.

The Stage C byte carrier now uses the same checked empty slots and
`byte_constants` lowering as the full Client. This avoids elaborating
the Lua body as thousands of nested byte constructors. The exported
body and SHA-1 contract is unchanged; artifact tests check the bytes
through the compiled Wasm exports.

Run `sh dev/m1-sets.sh` with the toolchain in `dev/TOOLCHAIN.md`. It runs
the complete Hash ladder, Set unit tests, artifact and type checks,
OCaml and LuaJIT comparisons, Wasm and Bash against temporary loopback
Redis, source mutants, the house audit and trusted-line gate. Every leg
runs, and any failing leg makes the final exit nonzero.

`python3 -P dev/sets-tests.py --offline` needs no listeners; `--static`
checks artifacts, typed refusals and the example interpreter entries.
Unit tests pin exact `int` replies and the stopped `Client` that a store
fault gives, every wrong Redis type, unchanged state on faults and
unrelated keys on success. The LuaJIT oracle checks every stored member
and cardinality; the store oracle checks the reply. Live read-only cases
use an ACL that denies ordinary EVAL and EVALSHA. The six documented
example commands run in the live leg. Mutants cover counts, last-member
deletion, both read commands, SADD write classification, the interpreter
error constructor and the Lua error tag, with passing unit and offline
controls before and after mutation.
