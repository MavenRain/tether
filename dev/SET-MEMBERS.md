# M1 Set enumeration

`smembers` reads every member of a Set key into an `array` of `bulk`
replies. Its arguments are erased result type `A`, erased tag `g`,
`Key Set g`, and a `Reply -> Script A g` continuation. Do-notation
supplies the continuation.

Redis [SMEMBERS](https://redis.io/docs/latest/commands/smembers/)
returns an unordered collection. Tether sorts that collection by unsigned
byte values, with a shorter prefix first, before exposing the reply to
Script code. This gives the store, LuaJIT, Node and Bash the same array.
The order is lexical, so `"10"` precedes `"2"`. It does not depend on
locale, Redis Set encoding, insertion order or UTF-8 decoding. Sorting
adds work beyond Redis's O(N) retrieval; each comparison may inspect a
common byte prefix.

Missing keys return an empty array and stay missing. Enumeration preserves
the stored Set and unrelated keys. Wrong-type keys return a typed `err`;
returning that error from an invocation stops the Client. Scripts may
inspect both arrays and errors using the existing reply constructors.
Captured arrays survive later removals in the same Script or Client.

Read-only enumeration uses EVALSHA_RO, with EVAL_RO fallback on NOSCRIPT.
A reachable write in a continuation or case arm still requires write
dispatch. Script command tag 28 is appended after LRANGE. Existing tags
keep their numbers.

All byte values remain bulk elements in the store and independent LuaJIT
twin. Valid UTF-8 arrays print as compact JSON on the text hosts. The Node
and REST hosts reject invalid UTF-8 with exit 4 and no stdout, preserving
the key. Existing resource and reply size limits still apply.

```sh
dune build bin/tether.exe
./tether exec examples/TeamRoster.tet --host node
./tether exec examples/TeamRoster.tet --entry retained --host bash
./tether exec examples/TeamRoster.tet --entry retained --host luajit
sh dev/m1-set-members.sh
```

Both example entries print `["alice","bob"]`. Enrollment adds Bob, Alice,
and a duplicate Alice. `retained` removes Alice after capturing the roster
and returns the earlier array. Each execution owns an empty temporary store.

The gate runs the complete List range ladder, then requires 14 unit cases,
six artifact pairs with identical Lua bodies, six typed refusals with no
published output, 16 store and 16 LuaJIT comparisons, 38 live host runs,
and six example executions. Of the live runs, 32 deny write-capable EVAL
commands, two reject invalid UTF-8, and two check unhandled error exits.
Wrong-type coverage on the live hosts includes String, Hash, List, ZSet
and Stream keys. The offline oracles cover the String, Hash and List keys.
The live fixtures add Set members in reverse reply order, so the reply
order comes from the lowering and not from the seed order.
The byte fixture covers all 256 byte values; another array has 129 members.
Nine compiled mutants must fail at their intended assertions, and four
controls must pass before and after mutation.

`python3 -P dev/set-members-tests.py --offline` omits listeners and host
executions. `--static` checks the artifacts, the refusals and the
interpreter examples only. `--artifacts` checks emission and write
classification only. `--probe ENTRY` checks one emitted entry against its
LuaJIT cases; the entries with cases are `all`, `head`, `earlier`,
`within` and `branch`. Partial runs have distinct summary rows and cannot
satisfy the complete ladder.

Lua remains at 320/320 lines and the store at 200/200. The shared array
adapter handles LRANGE, SMEMBERS and HGETALL. The two pinned preludes total
136 lines. See `dev/M1-BUILD-LOG.md` for measured validation results.
Set algebra, multi-member writes, random members and TTL are outside this slice.
