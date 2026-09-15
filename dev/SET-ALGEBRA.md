# M1 Set algebra

`sunion`, `sinter` and `sdiff` each take two `Key Set g` operands followed
by a `Reply -> Script A g` continuation. They have Script tags 32, 33 and
34. Both keys must have the command's tag. A wrong static Redis type or
tag on either key is rejected before any artifact is published.

The commands return `array` replies containing unique `bulk` members,
sorted by unsigned bytes with shorter prefixes first. Union includes
members of either input, intersection includes common members, and
difference includes members of the first input absent from the second.
Difference depends on operand order. Passing the same key twice gives
that Set for union and intersection, and an empty array for difference.
Missing keys count as empty Sets. A wrong stored Redis type on either
operand produces a catchable `err`, even if the other key is missing.
An uncaught error stops the Client and both hosts.

These are the two-key forms of Redis [SUNION](https://redis.io/docs/latest/commands/sunion/),
[SINTER](https://redis.io/docs/latest/commands/sinter/) and
[SDIFF](https://redis.io/docs/latest/commands/sdiff/). Variadic operands
remain future command work. The destination-writing forms are described
in `dev/SET-STORE.md`. This slice does not impose a new member-count bound.

The printer includes both keys in the artifact's declared key list and
deduplicates an identical pair. It calls Redis through `pcall` and uses
the existing deterministic array adapter. The independent OCaml store
uses Set union, intersection and difference over normalized members.
The LuaJIT twin computes membership independently and returns a fresh
array in reverse order, so the emitted adapter must sort it. Neither
implementation changes an input or creates a missing key. Tests compare
both complete stored values and an unrelated sentinel key.

All three commands are read-only. Reachable writes in a continuation or
case arm still remove `no-writes`. Both hosts use EVALSHA_RO and EVAL_RO
for a read-only invocation. Live tests disable EVAL and EVALSHA through
Redis ACLs to require the read-only dispatch path.
Replies retain their members after later Script or Client invocations
delete both inputs. The existing text hosts reject invalid UTF-8 output;
the store and LuaJIT twin preserve arbitrary member bytes.

`examples/TeamAccess.tet` demonstrates all three operations. Its `main`
entry returns `["alice","bob","carol"]`, `common` returns `["bob"]`,
`exclusive` returns `["alice"]`, and `retained` keeps `["bob"]` after
deleting the reviewers Set.

Run `sh dev/m1-set-algebra.sh` for the complete Hash projections ladder
and this slice. The added checks require 106 erased-interpreter cases,
24 identical artifact pairs, 36 type refusals with no output, four
interpreter examples, 90 LuaJIT cases, 234 live host runs over 114 cases
and six uncaught errors, 12 example executions, and 17 killed mutants
with six restored controls. The live runs include 216 read-only runs
and six expected invalid-UTF-8 refusals. All five wrong Redis types are
tested on both sides with the other key either missing or present.
Other fixtures cover empty bytes, prefixes, decimal-looking members,
all 256 byte values, 129 members, duplicate normalization, identical
keys, reversed operands, malformed erased operands, and retained replies.

The mutation runner requires a successful compile, the intended failing
assertion and exit status, and restored passing controls. It works in a
disposable copy. Targets cover every command selector, the second key,
member order, input preservation, key operand decoding, all read-only
tags, a reachable write, the emitted sort and bulk element tags.

The trusted line bounds and pinned foundation remain unchanged. SPEC
records the current prelude count. The build log records measured gate
results, including the independent M0 timing gate.

`python3 -P dev/set-algebra-tests.py --offline` runs without host
listeners. `--static` checks the artifacts, the refusals and the
interpreter examples only. `--probe ENTRY` checks one emitted entry
against its LuaJIT cases; the entries with cases are `union`, `inter`
and `diff`, each alone or with the suffix `Same`, `Reverse`, `Head`,
`Earlier`, `Within` or `Branch`. The `Raw` error entries have no LuaJIT
probe cases. Partial runs have distinct summary rows and cannot satisfy
the complete ladder.
