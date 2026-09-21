# M1 conditional List pushes

`lpushx Reply g key value` and `rpushx Reply g key value` push one byte
string onto an existing List. `lpushxMany Reply g key values` and
`rpushxMany Reply g key values` accept a nonempty `BulkArgs`, built with
`bulkOne` and `bulkMore`. Every form requires `Key List g`, and do-notation
supplies its `Reply -> Script Reply g` continuation. They append Script
tags 61, 62, 63 and 64; earlier tags retain their meanings.

The semantics follow [Redis LPUSHX](https://redis.io/docs/latest/commands/lpushx/)
and [Redis RPUSHX](https://redis.io/docs/latest/commands/rpushx/). Each form
emits a single atomic command. All four are writes, even if the key is
missing, so they use write dispatch. Their integer reply is the resulting
List length, or zero when the key is missing. Missing and expired keys stay
absent. Live keys of another type return WRONGTYPE and keep their complete
value and expiry.

Given `[old, tail]` and arguments `a, b, a, empty`, `lpushxMany` produces
`[empty, a, b, a, old, tail]`; `rpushxMany` produces
`[old, tail, a, b, a, empty]`. Values can be empty or arbitrary bytes.
Duplicates are retained. Existing expiry and unrelated keys are preserved.
Single-element bulk pushes agree with the scalar forms. The existing
`lpush`, `rpush`, `lpushMany` and `rpushMany` still create missing Lists.

`examples/ActiveQueue.tet` opens a queue and appends jobs conditionally.
`./tether exec examples/ActiveQueue.tet --host node` prints
`["open","welcome:alice","welcome:bob"]`. Its `priority` entry prepends
urgent jobs, `retained` returns the push count after a later invocation
deletes the queue, and `missing` returns zero without creating a queue.
The node, bash and luajit hosts accept the same example entries.

Run `sh dev/m1-list-conditional.sh` for the complete validation ladder,
including the preceding conditional Hash slice. The focused tests are
`dev/list_conditional_tests.exe`, `dev/list-conditional-tests.py` and
`dev/list-conditional-mutations.py`. The Python harness also supports
`--static`, `--offline` and `--probe ENTRY` for bounded checks.

The suite asserts 74 unit cases, 18 artifact pairs, 36 type refusals with
atomic output, 45 independent store and LuaJIT cases, and 118 node/bash
host runs. Those host runs include two invalid UTF-8 refusals, four
uncaught errors and eight expired-key checks. Four example entries run
on all three hosts. Eighteen compiling mutations cover conditional
creation, counts, expiry, interpreter dispatch, direction, bulk tails,
write classification and the independent Lua twin; five controls run
before mutation and after restoration. Existing mutation anchors follow
the shared dispatch changes without reducing their case inventories.

The trusted-source limits remain unchanged: Lua 320/320, store 200/200,
Bash 227/240, kernel 3997/4000 and encoder 246/600. See `dev/STRING-BYTES.md`
for the current prelude and fuel counts. At that slice the pinned preludes
totalled 188 lines after the List insertion slice, and Stage D measured
82228 checker/erasure polls followed by 12 static-walk polls; fuel 82234
had to fail with `SH-BUDGET` and publish no
output; the zero-fuel checker test remains. Disabling the printer guard
changes that failure to `CHECK budget`. The independent M0 timing gate
still requires a median strictly below 150 ms.

List bulk pops, other List commands, ZSet operations and the remaining
M1 examples and exporter gates remain separate work.
