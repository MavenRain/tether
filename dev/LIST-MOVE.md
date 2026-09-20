# M1 atomic List moves

```text
lmove Reply g source destination fromEnd toEnd continuation
```

Both keys require `Key List g`. Each endpoint has type `ListEnd`, with
constructors `listLeft` and `listRight`. Do-notation supplies the
continuation. The command appends Script tag 68, preserving all earlier
tags, and emits one atomic Redis LMOVE write. Both keys appear in the
artifact key list; an aliased key appears once. These scripts do not
carry the `no-writes` flag.

The behavior follows [Redis LMOVE](https://redis.io/docs/latest/commands/lmove/).
It removes an item from the selected source end, inserts it at the
selected destination end, and returns its bytes. A missing source
returns nil without inspecting or changing the destination. A missing
destination is created when a value moves. Moving the last source item
deletes that key and its expiry. Existing destination expiries survive;
a newly created destination has no expiry.

Moving within one List rotates it when the endpoints differ. Equal
endpoints leave its order unchanged. Every successful same-key move
preserves expiry, including a one-item List. A wrong-type source or a
wrong-type destination with a present source returns WRONGTYPE without
changing either key. Expired keys behave as absent.

Values are arbitrary bytes, including empty strings, NUL and all 256
byte values. The OCaml store and LuaJIT twin preserve them exactly.
The existing Node/Bash host rules refuse replies containing invalid
UTF-8 after Redis has performed the move. Bulk and nil replies remain
captured across later writes in the same Script and later Client calls.

`examples/QueueTransfer.tet` seeds a ready queue and moves its oldest job
into a processing queue. `main` prints `welcome:alice`; `retained` prints
the same value after deleting the processing queue. `rotated` moves the
last ready job to its front and prints `["welcome:bob","welcome:alice"]`.

Run `sh dev/m1-list-move.sh`. It includes the complete List insertion
ladder and requires these new inventories:

| Check | Required coverage |
| --- | --- |
| Store/interpreter units | 104 cases with complete values, deadlines and clock |
| Emitted artifact pairs | 14 entries, including computed endpoints and explicit continuations |
| Typed refusals | 18 cases, with no published output |
| Independent oracles | 48 store runs and 48 LuaJIT runs |
| Live Redis | 52 cases, 104 Node/Bash runs, 2 UTF-8 refusals, plus 4 command-error and 6 expired-key runs |
| QueueTransfer example | 9 Node/Bash/LuaJIT executions |
| Mutation tests | 14 killed, 0 surviving, 5 restored controls |

Mutation tests require every modified implementation to compile and
fail its intended semantic assertion. They cover both endpoints,
destination contents, source cleanup, expiry, atomic errors, nil replies,
interpreter decoding and dispatch, emitted operands, write classification
and the independent Lua twin.

Trusted-source limits remain unchanged: Lua 320/320, store 200/200,
Bash 227/240, kernel 3997/4000 and encoder 246/600. Adjacent declarations
share lines to retain these bounds. The pinned preludes total 193 lines.
Stage D measures 84753 checker/erasure polls and 12 static-walk polls;
fuel 84759 must fail with SH-BUDGET and publish no artifact. Runtime
budgets and the M0 timing bound remain unchanged. The build log records
the inherited ladder's result separately from the List move checks.
