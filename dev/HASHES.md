# M1 Hash commands

The Hash slice adds HSET, HGET, HDEL, HEXISTS, HLEN and HINCRBY.
`examples/Hashes.tet` updates a profile, counts visits exactly beyond 2^53,
reads a field in a separate read-only invocation and deletes both fields.

```sh
dune build bin/tether.exe
./tether exec examples/Hashes.tet --host node
./tether exec examples/Hashes.tet --host bash
./tether exec examples/Hashes.tet --host luajit
./tether exec examples/Hashes.tet --entry name --host node
./tether exec examples/Hashes.tet --entry deleted --host bash
```

The default entry prints `9007199254740993`, `name` prints `Alice`, and
`deleted` prints `0`. Each `exec` owns an empty temporary local store.

Every constructor starts with the erased result type `A` and tag `g`.
It ends with a `Reply -> Script A g` continuation, supplied by do-notation.

| Constructor | Runtime operands | Successful reply |
| --- | --- | --- |
| `hset` | `Key Hash g`, field `Bytes`, value `Bytes` | `int` 1 for a new field, 0 for replacement |
| `hget` | `Key Hash g`, field `Bytes` | `bulk` value, or `nil` for a missing field or key |
| `hdel` | `Key Hash g`, field `Bytes` | `int` 1 for a removed field, 0 if absent |
| `hexists` | `Key Hash g`, field `Bytes` | `int` 1 for a present field, 0 if absent |
| `hlen` | `Key Hash g` | `int` field count, 0 for a missing key |
| `hincrby` | `Key Hash g`, field `Bytes`, `Signed64` | `int` exact new value |

HSET preserves other fields. HDEL removes the key when it removes the
last field. Empty fields and values are valid; an empty value is distinct
from a missing field. Hash commands reject keys holding another Redis
type, even when external writes have broken the schema's promise.
These behaviors follow Redis's [HSET](https://redis.io/docs/latest/commands/hset/)
and [HDEL](https://redis.io/docs/latest/commands/hdel/) contracts.

HINCRBY takes the checked `int64 b"..."` literal and starts a missing
field at zero. A stored value must be a canonical signed decimal within
64 bits. Invalid stored decimals produce `ERR hash value is not an
integer`; overflow produces `ERR increment or decrement would overflow`.
Failures preserve every field. After Redis accepts HINCRBY, the generated
Lua reads the exact decimal back with HGET, avoiding Lua number rounding.
The typed integer crosses both artifact boundaries as a bulk string.
The arithmetic range follows Redis's
[HINCRBY](https://redis.io/docs/latest/commands/hincrby/) contract.

Fields and stored values preserve arbitrary bytes, including NUL and
non-UTF-8 octets. The OCaml interpreter and LuaJIT can return those bytes.
The existing Node and REST text hosts reject non-UTF-8 replies with exit
4; valid UTF-8, NUL, BOM and trailing newlines survive. This is the host
restriction documented in `dev/STAGE-E.md`. A rejected reply does not
roll back effects that Redis already performed.

HGET, HEXISTS and HLEN join the explicit read-only allowlist. HSET, HDEL
and HINCRBY require write-capable dispatch. Classification includes every
reachable branch and closure capture. Script errors remain typed `err`
replies; a Script can inspect them, and an error returned from an
invocation stops the Client.

The original Hash slice supports one field per command. HGETALL is now
available in `dev/HASH-ENTRIES.md`. Multi-field writes, field expiry and
key TTL remain future work. The profile example
does not implement the remaining M1 session-store application.

The Hash slice appended six constructors, preserving existing tags.
At its close the two preludes totaled 121 lines, with trusted counts
Lua 305/320 and store 165/200. The subsequent Set slice and current
counts are documented in `dev/SETS.md` and `SPEC.md`.

Run `sh dev/m1-hashes.sh` with the toolchain in `dev/TOOLCHAIN.md`.
It runs the complete String ladder, the Hash build and unit suite,
artifact/type checks, OCaml and LuaJIT comparisons, actual Wasm and Bash
executions against temporary loopback Redis, source mutants, house audit
and trusted-line gate. All legs run and their failures affect the final
exit status. `python3 -P dev/hashes-tests.py --offline` needs no listeners;
`--static` checks artifacts, types and the example interpreter entries.

Tests check exact reply variants in the OCaml interpreter, success and
fault alike: every fault of every command is an `err` reply that stops
the Client, and the unit suite requires that stop with the exact message.
Tests check every stored field in both the LuaJIT twin and live Redis.
Live read-only cases use an ACL that denies ordinary EVAL and EVALSHA.
The five documented `exec` forms of the example run in the live leg and
print `PASS HASHES-EXAMPLE exec=5`. Mutation controls cover HGET
classification, HSET replacement counts, deletion of the last field,
HINCRBY precision, the `err` reply constructor of the interpreter and the
hash fault message, with passing controls before and after mutation.
