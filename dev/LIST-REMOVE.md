# M1 List removal

`lrem Reply g key count value` removes occurrences of a byte string from
`Key List g`. The count has type `Signed64`, and do-notation supplies the
`Reply -> Script Reply g` continuation. LREM appends Script tag 65;
earlier tags retain their meanings. It emits one atomic write command,
including when no key or matching value exists.

The semantics follow [Redis LREM](https://redis.io/docs/latest/commands/lrem/).
A positive count removes at most that many matches from the head. A
negative count removes at most its magnitude from the tail. Zero removes
every match. The reply is the number removed, and all other values retain
their order. Given `[a,b,a,c,a]`, counts `1`, `-1` and `0` produce
`[b,a,c,a]`, `[a,b,a,c]` and `[b,c]`, with replies `1`, `1` and `3`.

Empty strings and arbitrary bytes are valid values. Counts are passed
as canonical decimal bytes without converting them to Lua numbers.
Redis accepts counts from `-9223372036854775807` to `9223372036854775807`.
The minimum signed value, `-9223372036854775808`, returns Redis's range
error before key lookup, including on missing or wrong-type keys. The
store and independent Lua twin reproduce that error without changing
state. The twin bounds the magnitude by the List length before converting
it to a number.

Remaining Lists preserve their expiry. Removing the final item deletes
both the key and its expiry. Missing and expired keys return zero and
stay absent. Live keys of another type return WRONGTYPE without changing
their value or expiry. Count validation precedes key lookup and type
checking. Surface `int64` literals reject malformed or out-of-range
counts; the store and Redis also reject invalid constructed payloads.
Unrelated keys remain intact.

`examples/QueueCleanup.tet` seeds a queue, removes cancelled jobs and
returns `["welcome:alice","welcome:bob"]`. The `removed` entry returns
`2`; `retained` returns the same reply after a later invocation deletes
the queue. All three entries run through node, bash and luajit hosts.

Run `sh dev/m1-list-remove.sh` for the complete ladder, including the
preceding conditional List slice. Focused checks are:

```sh
dune build -j 2 bin/tether.exe dev/store_run.exe dev/list_remove_tests.exe
_build/default/dev/list_remove_tests.exe
python3 -P dev/list-remove-tests.py
python3 -P dev/list-remove-mutations.py
```

The unit suite checks 135 cases, including full state and expiry, signed
extremes, malformed counts, every wrong Redis type and malformed operand
shapes. Integration covers 18 artifact pairs, 17 atomic refusals, 41 store
and 41 LuaJIT cases, and 47 live scenarios across both generated hosts.
The 104 host runs include two UTF-8 output refusals, four uncaught errors
and six expired-key checks. Nine example runs cover all three hosts.
Fourteen compiling mutants must fail their intended assertions, with
five controls repeated after restoration.

Existing source bounds remain unchanged: Lua 320/320, store 200/200,
Bash 227/240, kernel 3997/4000 and encoder 246/600. Adjacent small helper
declarations share lines to keep the existing bounds. Both pinned
preludes total 186 lines. Stage D uses 77890 checker/erasure polls and
12 static-walk polls; fuel 77896 must fail with `SH-BUDGET` without
publishing an artifact. The runtime budget and timing bounds are unchanged.
This slice does not complete M1 or ratify M0-EXIT. The build log records
actual validation results, including any independent timing failure.
