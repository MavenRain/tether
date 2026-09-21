# M1 String bytes

`append` and `strlen` append Script tags 71 and 72, preserving all earlier
constructor tags. Each takes the erased result type `A` and ends with a
`Reply -> Script A g` continuation. Do-notation supplies that continuation.

| Constructor | Erased parameters after `A` | Runtime operands | Reply |
| --- | --- | --- | --- |
| `append` | `g : Tag` | `Key (Str Binary) g`, `Bytes` | `int` with the resulting byte length |
| `strlen` | `e : Encoding`, `g : Tag` | `Key (Str e) g` | `int` with the existing byte length |

APPEND concatenates bytes in order. A missing or expired key starts as an
empty String, including when appending zero bytes. An existing key keeps
its absolute expiry; a newly created key is persistent. STRLEN returns
zero for a missing or empty String and leaves its state unchanged. Both
commands return WRONGTYPE for non-String values, preserving the complete
value and expiry. A Script can catch the error; an unhandled error stops
the Client.

Lengths count bytes, including NUL and non-UTF-8 bytes. Numeric-looking
values are never parsed as numbers. `strlen` accepts Int64 keys as well
as Binary keys; `append` requires a Binary key because arbitrary bytes
would invalidate the Int64 encoding. Captured replies retain the length
at the time of the command across later writes and Client invocations.

These behaviors follow Redis [APPEND](https://redis.io/docs/latest/commands/append/)
and [STRLEN](https://redis.io/docs/latest/commands/strlen/). The local
store and LuaJIT oracle enforce the default 512 MiB String size limit
before concatenation, returning
`ERR string exceeds maximum allowed size (proto-max-bulk-len)`.
Live Redis uses its configured limit. Custom server size limits are not
modeled by the local store. Boundary tests exercise the size predicate
without allocating a 512 MiB payload. One store-level case appends one
268435457 byte String to itself and requires the size error at the
append call site.

STRLEN uses the read-only Lua flag and EVALSHA_RO dispatch. APPEND uses
write-capable dispatch. No host protocol or reply representation changes.

```sh
./tether exec examples/StringBuffer.tet --host node
./tether exec examples/StringBuffer.tet --entry length --host bash
./tether exec examples/StringBuffer.tet --entry retained --host luajit
./tether exec examples/StringBuffer.tet --entry integerLength --host node
```

The entries print `hello, world`, `12`, `5` and `16`, respectively.

`sh dev/m1-string-bytes.sh` runs the inherited List pop ladder and:

- 60 store and interpreter cases, including full state and expiry checks,
  malformed operands, the size boundary and the size limit at the append
  call site.
- 11 artifact pairs and 15 typed refusals with no output published.
- 45 cases checked against both the store and independent LuaJIT model.
  A LuaJIT reply mismatch reports the label `STRING-BYTES LuaJIT reply`.
- 51 live Redis cases on both Node/Wasm and Bash, plus four unhandled
  errors and four expired-key checks. Read-only cases deny EVAL/EVALSHA.
- All four example entries through Node/Wasm, Bash and LuaJIT.
- 15 compiling semantic mutants and three restored controls.

Trusted limits remain Lua 320/320 and store 200/200. The compact helper
layout keeps those existing limits; no bound is raised. The two trusted
preludes total 197 lines and remain pinned in `dev/PRELUDES.sha256`.
The checker and erasure use 93751 polls for `M0Spine.tet`; the printer
walk uses 12 more. Stage D keeps both its zero-fuel CHECK refusal and its
distinct SH-BUDGET refusal, now at fuel 93757.

The new feature checks passed on 2026-09-21. The separate M0 timing
measurement failed at 253.674 ms against the unchanged 150 ms bound.
The complete inherited ladder was not run for this slice. Scoped
regression results and full capture paths are in `dev/M1-BUILD-LOG.md`.
