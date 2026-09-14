# M1 Hash enumeration

`hgetall` reads every field and value of a Hash key into an `array` of
`bulk` replies. Its arguments are erased result type `A`, erased tag `g`,
`Key Hash g`, and a `Reply -> Script A g` continuation. Do-notation
supplies the continuation.

Redis [HGETALL](https://redis.io/docs/latest/commands/hgetall/) returns
alternating fields and values in RESP2. Tether sorts the pairs by unsigned
field bytes, with shorter prefixes first. Each value follows its own
field. Values remain bytes, including decimal strings beyond 2^53.
For `{z: A, a: Z}`, the reply is `["a","Z","z","A"]`. Ordering does
not depend on locale, Hash encoding, insertion order or UTF-8 decoding.
The emitted Lua sorts the pairs, which adds O(N log N) comparisons beyond
Redis's O(N) retrieval, where N counts fields; each comparison may inspect
a common byte prefix. The store returns the bindings already in field
order. The reply has 2N elements.

Missing keys return an empty array and stay missing. Reads preserve the
Hash and unrelated keys. Wrong-type keys produce a typed `err`, which a
Script may inspect. Returning that error from an invocation stops the
Client. Captured arrays survive subsequent updates or deletions in the
same Script or a later Client invocation.

Read-only enumeration uses EVALSHA_RO, with EVAL_RO fallback on NOSCRIPT.
A write reachable through a continuation or case arm still requires write
dispatch. Script command tag 29 follows SMEMBERS; existing tags keep
their numbers.

All byte values remain bulk elements in the store and independent LuaJIT
twin. Valid UTF-8 arrays print as compact JSON on the text hosts. Invalid
UTF-8 in either fields or values makes the Node and REST hosts exit 4
with no stdout, preserving the key. Existing resource and reply-size
limits still apply.

```sh
dune build bin/tether.exe
./tether exec examples/HashSnapshot.tet --host node
./tether exec examples/HashSnapshot.tet --entry retained --host bash
./tether exec examples/HashSnapshot.tet --entry retained --host luajit
sh dev/m1-hash-entries.sh
```

Both example entries print `["name","Alice","visits","9007199254740993"]`.
`retained` changes the stored name to Alicia after capturing the profile,
then returns the original array. Each execution owns an empty temporary
store. This example does not implement the remaining session-store application.

The gate runs the complete Set enumeration ladder, then requires 15 unit
cases, seven artifact pairs with identical Lua bodies, six type refusals
with no published output, 19 store and 19 LuaJIT comparisons, 44 live host
runs, and six example executions. Of the live runs, 38 deny write-capable
EVAL commands, four reject invalid UTF-8, and two check unhandled errors.
Wrong-type coverage includes String, List, Set, ZSet and Stream keys;
the offline integration oracles cover the first three, and unit and live
tests cover all five. Live and LuaJIT fixtures enumerate fields in an
order different from the expected reply. Fixtures cover all 256 byte
values in fields and values, empty bytes, prefix order, and 129 fields.
Eleven compiled mutants must fail at their intended assertions. Four
controls must pass both before and after mutation.

`python3 -P dev/hash-entries-tests.py --offline` omits listeners and host
executions. `--static` checks artifacts, refusals and interpreter examples.
`--artifacts` checks emission and write classification. `--probe ENTRY`
checks one emitted entry against its LuaJIT cases: `all`, `head`, `value`,
`earlier`, `within` or `branch`. Partial modes have distinct summary rows
and cannot satisfy the complete ladder.

Lua remains at 320/320 lines and the store at 200/200. The shared array
adapter sorts element or pair indices, then preserves the elements within
each pair. LRANGE retains its sequence order. Shared Hash update handling
preserves HSET and HDEL counts. The two pinned preludes total 136 lines.
Multi-field writes, other Hash bulk commands, field expiry and key TTL
remain future work. Measured validation is in `dev/M1-BUILD-LOG.md`.
