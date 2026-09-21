# M1 List insertion

The commands accept a List key, pivot bytes, inserted bytes and a
continuation:

```text
linsertBefore Reply g key pivot value continuation
linsertAfter  Reply g key pivot value continuation
```

Both require `Key List g`. Do-notation supplies the continuation.
They append Script tags 66 and 67; all earlier tags retain their meanings.
Each emits one atomic Redis LINSERT write, including an unsuccessful
insertion. Their Lua bodies do not carry the `no-writes` flag.

The semantics follow [Redis LINSERT](https://redis.io/docs/latest/commands/linsert/).
The first matching pivot is selected from the head. BEFORE inserts just
before that item; AFTER inserts just after it. The reply is the new
length, `0` for an absent key, or `-1` when an existing List has no pivot.
Neither unsuccessful case creates or changes a key.
For `[a,b,a]`, inserting `x` around `a` yields `[x,a,b,a]` or `[a,x,b,a]`,
with reply `4`. A wrong-type key returns WRONGTYPE without changing state.
An expired key behaves as absent. Successful insertion preserves expiry.

Pivots and inserted values are byte strings, including empty strings,
NUL, invalid UTF-8 and all 256 byte values. Decimal-looking bytes compare
exactly: `01` differs from `1`. Returning an array containing invalid
UTF-8 still follows the existing host refusal rules after the write.
Integer replies remain captured values across later writes in the same
Script and across later Client invocations.

`examples/QueueInsert.tet` seeds two jobs, inserts a priority job before
`welcome:bob`, and inserts an audit job after it. Its main entry prints
`["welcome:alice","priority:carol","welcome:bob","audit:bob"]`; its length
entry returns `4`, and its missingPivot entry returns `-1`.

Run `sh dev/m1-list-insert.sh`. It includes the complete List removal
ladder and requires these new inventories:

| Check | Required coverage |
| --- | --- |
| Store and interpreter units | 50 cases, including complete state and deadlines |
| Emitted artifact pairs | 17 entries |
| Typed refusals | 16 cases, with no published artifacts |
| Independent oracles | 31 store runs and 31 LuaJIT runs |
| Live Redis | 35 cases, 78 Node/Bash runs, including 2 UTF-8 refusals, 4 unhandled errors and 4 expired-key runs |
| QueueInsert example | 9 Node/Bash/LuaJIT executions |
| Mutation tests | 14 killed, 0 surviving, 5 restored controls |

The mutation runner compiles each altered implementation and requires its
intended semantic assertion to fail. It covers placement, pivot matching,
prefix order, length replies, absent keys and pivots, expiry, interpreter
dispatch, emitted operands, write classification and the independent twin.

Trusted-source limits remain unchanged: Lua 320/320, store 200/200,
Bash 227/240, kernel 3997/4000 and encoder 246/600. Adjacent small
declarations share lines to retain these bounds. At that slice the pinned
preludes totalled 188 lines and Stage D measured 82228 checker/erasure
polls and 12 static-walk polls; fuel 82234 had to fail with SH-BUDGET and
publish no artifact. See `dev/LIST-POP.md` for the current prelude and
fuel counts. Runtime budgets and timing bounds remain unchanged.
This slice leaves the remaining M1 work and M0-EXIT status to their gates.
