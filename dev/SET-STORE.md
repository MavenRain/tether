# M1 Set store commands

`sunionstore`, `sinterstore` and `sdiffstore` take a destination followed
by two source keys. All three operands have type `Key Set g` with the
same tag. The final argument is a `Reply -> Script A g` continuation.
The commands have Script tags 35, 36 and 37. A static type or tag
mismatch on any operand fails before publishing an artifact.

These are the forms of Redis [SUNIONSTORE](https://redis.io/docs/latest/commands/sunionstore/),
[SINTERSTORE](https://redis.io/docs/latest/commands/sinterstore/) and
[SDIFFSTORE](https://redis.io/docs/latest/commands/sdiffstore/) with two
source keys. Variadic operands remain future work.

The result replaces the destination and the `int` reply contains its
cardinality. Missing inputs count as empty Sets. An empty result deletes
the destination. An existing destination may contain any Redis type;
successful replacement also clears its expiry. When a destination is
also an input, it must be missing or contain a Set. Both inputs are read
before replacement, so either or both may alias the destination.
Difference uses the first source minus the second.

A wrong stored type on either input produces a catchable `err` even when
the other input is missing. The destination and both sources retain their
complete values on error. An uncaught error stops the Client before its
next invocation. A successful command returns a count that remains
available after subsequent writes or deletion of the destination.

All three commands may write. Their artifacts use EVALSHA with EVAL on
NOSCRIPT, including when the inputs are empty. Key declarations include
the destination and both inputs with duplicates removed. The Wasm and
Bash artifacts carry identical Lua bodies. The existing integer reply
adapter formats the count. The store and LuaJIT twin reuse their own
independent Set operations and update the destination after both input
type checks. Arbitrary member bytes can be stored without crossing the
text reply boundary. Returning members later has the existing UTF-8
limits described in `dev/SET-MEMBERS.md`.

`examples/TeamCache.tet` has three entries:

| Entry | Behavior | Output |
| --- | --- | --- |
| `main` | Cache a union and read its members. | `["alice","bob","carol"]` |
| `retained` | Keep an intersection count after deleting the destination. | `1` |
| `exclusive` | Replace the first input with its difference. | `["alice"]` |

## Validation

Run `sh dev/m1-set-store.sh` for the complete Set algebra ladder followed
by this slice. The added checks require 322 erased-interpreter cases,
33 matching artifact pairs, 54 type refusals with absent output,
three interpreter examples, 201 LuaJIT cases, 564 live host runs
covering 279 fixtures and six uncaught errors, nine example executions,
and 18 killed mutants with six restored controls.

Cases cover destination aliasing, identical and reversed inputs,
empty results, replacement of every Redis type, all five wrong input
types, missing inputs, retained counts, reply constructors, all 256 byte
values, empty members, prefixes, duplicate normalization, 129 members,
and malformed erased operands. Live runs compare complete preserved
values, result members, an unrelated sentinel and expiry behavior.
They disable EVAL_RO and EVALSHA_RO through Redis ACLs to require the
write dispatch path. The store has no expiry model; expiry checks run
against Redis on both hosts.

`python3 -P dev/set-store-tests.py --offline` runs artifacts, refusals,
interpreter examples and the LuaJIT cases without opening listeners.
`--static` omits LuaJIT too. `--probe ENTRY` runs one emitted entry
against its LuaJIT fixtures; the `Raw` entries and unknown entries have
no probe fixtures and are rejected. Partial modes have distinct summary
rows and cannot satisfy the full ladder.

The mutation battery uses a disposable copy. Each mutant must compile,
exit with the required test failure, and report the intended assertion.
Restored controls must then pass. Mutations cover command selection,
source and destination operands, empty deletion, counts, aliasing, reply
tags and write classification. The earlier Set algebra difference
mutation now anchors its own dispatch branch because both command
families use the same Set difference function.
The List trim empty-key mutation selects the List value explicitly,
since the Set store helper also removes empty results. Its assertion
and required failure are unchanged.

The foundation pin and trusted line bounds are unchanged. SPEC records
the current prelude count. The build log records measured results,
including the independent M0 timing gate.
