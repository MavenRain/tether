# M1 String and key commands

The String slice adds SET, INCRBY, DECR, DEL and EXISTS to INCR and GET.
`examples/Strings.tet` demonstrates exact arithmetic, byte-string storage
and deletion. Run it with any local host:

```sh
dune build bin/tether.exe
./tether exec examples/Strings.tet --host node
./tether exec examples/Strings.tet --host bash
./tether exec examples/Strings.tet --host luajit
./tether exec examples/Strings.tet --entry binary --host node
./tether exec examples/Strings.tet --entry deleted --host bash
```

The default entry prints `9007199254740993`, `binary` prints `hello`, and
`deleted` prints `0`. Every invocation starts with an empty local store.

Each constructor starts with the erased result type `A`, then the erased
parameters listed below. It ends with a `Reply -> Script A g` continuation.
Do-notation supplies that continuation.

| Constructor | Erased parameters | Runtime operands | Successful reply |
| --- | --- | --- | --- |
| `set` | `g : Tag` | `Key (Str Binary) g`, `Bytes` | `status b"OK"` |
| `setInt64` | `g : Tag` | `Key (Str Int64) g`, `Signed64` | `status b"OK"` |
| `incrby` | `g : Tag` | `Key (Str Int64) g`, `Signed64` | `int` with exact new value |
| `decr` | `g : Tag` | `Key (Str Int64) g` | `int` with exact new value |
| `del` | `t : RedisType`, `g : Tag` | `Key t g` | `int` containing 0 or 1 |
| `exists` | `t : RedisType`, `g : Tag` | `Key t g` | `int` containing 0 or 1 |

`setInt64` accepts the existing checked `int64 b"..."` literal. Both SET
constructors issue unconditional SET, replacing an existing value of any
Redis type. Bytes, including NUL and non-UTF-8 octets, survive storage.
The existing host reply-text restrictions still apply when returning a
binary payload to stdout.

INCRBY and DECR start missing keys at zero. Wrong-type values, invalid
stored decimals and signed overflow produce an `err` reply, preserving
the stored value. A Script can inspect that reply and continue. An error
returned from an invocation stops the Client, as for INCR and GET.
After a successful arithmetic command, the Lua runtime reads the decimal
value with GET, avoiding Lua number rounding. A missing key at that read
answers `nil`, the same reply GET answers for a missing key. Int replies
cross the artifact boundaries as bulk strings, including DEL and EXISTS
counts. The Lua runtime formats the count the server reports, and a
count reply that is not an integer becomes an `err` reply.
These behaviors follow Redis's [SET](https://redis.io/docs/latest/commands/set/),
[INCRBY](https://redis.io/docs/latest/commands/incrby/),
[DECR](https://redis.io/docs/latest/commands/decr/),
[DEL](https://redis.io/docs/latest/commands/del/) and
[EXISTS](https://redis.io/docs/latest/commands/exists/) contracts.

EXISTS joins GET and `pure` in the explicit read-only allowlist. Every
other new constructor requires write-capable dispatch. Classification
includes all reachable branches and closure captures. DEL and EXISTS
accept one key of any admitted schema type. TTL, SET options and
multi-key command forms remain outside this slice.

The Redis prelude appends six constructors, preserving the existing
constructor tags, and its checksum is updated in `dev/PRELUDES.sha256`.
The two preludes total 115 lines. The vendored kernel and reactor remain
at their existing pin. Current trusted counts are Lua 294/320 and store
136/200; the other measured groups and all bounds are unchanged.

Run `sh dev/m1-strings.sh` with the toolchain in `dev/TOOLCHAIN.md`.
It runs the complete read-only ladder, 46 store checks, nine artifact
pairs, typed refusals, independent LuaJIT and store execution, and the
two actual hosts against temporary localhost Redis. Every leg runs and
the final exit status includes every failure. `python3 -P
dev/strings-tests.py --offline` runs without listeners, while `--static`
checks artifacts, types and the example interpreter entries only.

The store unit suite checks both reply values and the resulting immutable
store. The LuaJIT twin uses independent signed decimal-digit arithmetic.
Live cases verify the stored values after each host execution. The
EXISTS cases run with an ACL that refuses ordinary EVAL and EVALSHA.
The mutation runner checks precision, overflow, deletion and read-only
classification, then requires the restored controls to pass.
