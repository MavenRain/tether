# M1 Set member transfers

`smove Reply g source destination member` has a final
`Reply -> Script Reply g` continuation. Both keys have type `Key Set g`
with the same tag, and the member has type `Bytes`. It is Script tag 38.
Do-notation supplies the continuation in the usual way. Wrong key types,
key tags and member types fail before either artifact is published.

The Redis [SMOVE](https://redis.io/docs/latest/commands/smove/) command
returns an `int` containing `1` when the member was present in the source,
including when it already exists at the destination. Otherwise it returns
`0`. Removing the last source member deletes the source. A destination
created by a successful transfer has no expiry. Existing Sets retain
their exact expiry deadlines while they survive.

A missing source returns `0` without checking the destination type.
An existing source requires both stored values to be Sets, even when
the member is absent. A same-key transfer returns its membership result
and leaves the Set unchanged. Wrong stored types produce a catchable
`err` with both complete values unchanged. An uncaught error stops the
Client before its next invocation.

The command is classified as writing even when the source is missing
or both operands name the same key. Both artifacts use EVALSHA with EVAL
on NOSCRIPT. Declared keys include both operands with duplicates removed.
Wasm and Bash carry identical Lua bodies. Transfers support arbitrary
member bytes because the command returns an integer. Subsequent member
enumeration retains the existing UTF-8 reply limits in `dev/SET-MEMBERS.md`.

The interpreter implements the transfer through persistent Set updates.
A shared typed lookup supplies the missing-key defaults for Strings,
Hashes, Sets and Lists. The LuaJIT twin has its own transfer implementation.
The store remains at 200/200 lines and the Lua printer group at 320/320.

## Example

`examples/TeamTransfer.tet` provides three entries:

| Entry | Behavior | Output |
| --- | --- | --- |
| `main` | Transfer Alice from blue to green, then enumerate green. | `["alice","carol"]` |
| `retained` | Keep the transfer result after deleting green. | `1` |
| `unchanged` | Transfer Alice within blue. | `1` |

## Validation

Run `sh dev/m1-set-move.sh` for the complete Set store ladder followed
by this slice. Every command exit status and each expected summary row
must pass. The added inventory is:

- 304 store/interpreter cases, including all byte values, empty members,
  aliases, all five wrong types, malformed operands and exhausted fuel.
- 12 artifact pairs and 14 static refusals with no output publication.
- 113 independent LuaJIT cases checking complete values and replies.
- 179 live Redis cases on both hosts, plus two uncaught-error checks,
  for 360 host executions. The cases cover both operand orders, missing
  sources, no-op errors, same-key transfers, binary and quoted members,
  retained replies, complete values and exact expiry deadlines. Redis ACLs
  disable read-only EVAL variants to check write dispatch.
- Three interpreter example entries and nine executions across Node,
  Bash and LuaJIT.
- 15 compiling mutations, zero survivors and five restored controls.

The prelude pin is updated. SPEC records the current prelude count.
The measured Stage D checker/erasure cost is
30471 polls, followed by 12 static-walk polls. Its refusal still gives the
walk six polls and requires `SH-BUDGET`, at fuel 30477. Legacy Set algebra
and Set store mutation anchors retain their original semantic changes
after the shared lookup and Lua dispatch edits. The unknown-tag probe now
uses 39, after SMOVE claimed 38.

The pure store and LuaJIT twin do not model time. Expiry assertions run
against local Redis. TTL commands, variadic Set operands, other bulk
operations, ZSets and the remaining M1 milestones are still pending.
