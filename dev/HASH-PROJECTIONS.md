# M1 Hash projections

`hkeys` returns a Hash key's fields, and `hvals` returns its values. Both
produce an `array` of `bulk` replies sorted by unsigned bytes, with shorter
prefixes first. HVALS preserves duplicates: `{z: x, a: x, b: y}` produces
`["x","x","y"]`. Sorting values is independent of field order. Use
HGETALL to retain field/value associations; zipping HKEYS with HVALS does
not recover those associations.

Each command takes erased result type `A`, erased tag `g`, `Key Hash g`,
and a `Reply -> Script A g` continuation. Do-notation supplies the
continuation. HKEYS has Script tag 30 and HVALS has tag 31, following
HGETALL. Existing tags keep their numbers.

Missing keys return empty arrays and stay missing. Wrong types produce
a typed `err`, which a Script may inspect. Returning the error from an
invocation stops the Client. Reads leave the Hash and unrelated keys
unchanged. Arrays retained across later writes in the same Script or
subsequent Client invocations preserve their captured contents.

The Lua adapter calls the corresponding Redis command and sorts its
returned elements with the existing byte comparator. The independent
store projects its Hash bindings and sorts the selected strings. The
LuaJIT twin creates fresh reply tables in reverse field order. Sorting
adds O(N log N) comparisons to enumeration, where N counts fields; each
comparison may inspect a common byte prefix. HVALS keeps one element per
field even when values repeat.

Read-only projections use EVALSHA_RO and EVAL_RO fallback on NOSCRIPT.
A reachable write in a continuation or case arm still requires write
dispatch. Both artifact types carry identical canonical Lua bodies.

The interpreter and LuaJIT support every byte value. Node and Bash text
hosts print valid UTF-8 arrays as compact JSON. Invalid UTF-8 in a returned
element causes exit 4 with no stdout. Bytes in omitted values do not
affect HKEYS, and bytes in omitted fields do not affect HVALS. Decimal
strings, including values beyond 2^53, remain exact bulk strings.
Existing resource and reply-size limits apply.

```sh
dune build bin/tether.exe
./tether exec examples/HashCatalog.tet --host node
./tether exec examples/HashCatalog.tet --entry retained --host bash
./tether exec examples/HashCatalog.tet --entry retained --host luajit
sh dev/m1-hash-projections.sh
```

The main example prints `["name","plan","role"]`. The `retained` entry
captures `["Alice","member","member"]`, deletes the Hash, and returns
the captured values. Each execution owns an empty temporary store.

The gate runs the complete Hash enumeration ladder, then requires 36 unit
cases, 12 matching artifact pairs, 12 type refusals with no published output,
38 interpreter and 38 LuaJIT cases, 88 live Node/Bash host runs, and six
example executions. The live cases include 76 runs that deny write-capable
EVAL commands, six UTF-8 refusals and four unhandled errors. Unit and live
tests cover String, List, Set, ZSet and Stream wrong types. Fixtures cover
empty bytes, prefixes, decimal byte ordering, all 256 byte values,
duplicate values, complete 129-field replies and retained arrays.
Sixteen compiled mutants must fail at their intended assertions; six
controls must pass before and after mutation. The store keeps Hash fields
in unsigned byte order, so the shared sort changes only the value
projection. The KEYS-ORDER mutant reverses the field projection and pins
the HKEYS order.

`python3 -P dev/hash-projections-tests.py --offline` runs without host
listeners. `--static` checks artifacts, refusals and interpreter examples.
`--artifacts` checks emission and write classification. `--probe ENTRY`
checks one entry against its LuaJIT cases: `keys`, `keysHead`,
`keysEarlier`, `keysWithin`, `keysBranch`, or the corresponding `vals`
entry. Raw error entries have no LuaJIT probe cases. Partial modes have
distinct summary rows and cannot satisfy the full ladder.

Lua remains at 320/320 lines and the store at 200/200. Existing store reply
helpers use compact layout to accommodate the shared Hash projection
helper and dispatch branch. `SPEC.md` records the current prelude count.
TTL, other bulk Hash commands and the remaining M1 milestones stay in
`SPEC.md`. Measured validation is recorded in `dev/M1-BUILD-LOG.md`.
