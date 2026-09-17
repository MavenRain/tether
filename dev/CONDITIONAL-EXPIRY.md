# M1 conditional expiry

The new Script constructors accept any `Key t g` and preserve its type
and tag indices:

| Constructor | Arguments after `Reply` | Script tag |
| --- | --- | --- |
| `expireIf` | `t g key seconds condition` | 48 |
| `pexpireIf` | `t g key milliseconds condition` | 49 |
| `expireatIf` | `t g key unixSeconds condition` | 50 |
| `pexpireatIf` | `t g key unixMilliseconds condition` | 51 |

The amount has type `Signed64`; the condition has type `ExpiryCondition`.
Each constructor ends with a `Reply -> Script Reply g` continuation,
which do-notation supplies. The existing unconditional constructors keep
their signatures and tags.

| Condition | Update allowed when |
| --- | --- |
| `expiryNX` | The key has no expiry. |
| `expiryXX` | The key already has an expiry. |
| `expiryGT` | The proposed deadline is later than the current deadline. |
| `expiryLT` | The proposed deadline is earlier than the current deadline. |

A persistent key has an infinite deadline for GT and LT. Equal deadlines
fail both comparisons. Missing keys return integer `0`. An accepted update
returns integer `1`; a rejected update returns `0` and preserves the value
and deadline. These rules follow Redis's
[EXPIRE conditions](https://redis.io/docs/latest/commands/expire/)
and [EXPIREAT conditions](https://redis.io/docs/latest/commands/expireat/).

Each call accepts one condition. Byte strings and extra condition arguments
are rejected during checking. This slice does not expose combinations such
as XX with GT. Wrong key types, different key tags and invalid signed
literals also fail before output publication.

## Deadlines and errors

Relative expiry adds the current clock before comparing deadlines.
Absolute expiry compares the timestamp directly. Comparisons remain exact
across the entire signed 64-bit range, including adjacent milliseconds
above 2^53. Arguments reach Redis as decimal strings.

An accepted deadline at or before the clock deletes the key. A condition
that rejects that deadline preserves the key. Conversion and clock-addition
overflow produce the existing command error before the missing-key or
condition checks. Errors remain catchable Script replies. An uncaught
error stops later Client invocations.

All four constructors use write dispatch, including calls that return `0`.
Wasm and Bash contain identical canonical Lua bodies and declare each key
once. The store and independent LuaJIT twin maintain the same condition
semantics. See `TTL.md` and `ABSOLUTE-EXPIRY.md` for clock and reply limits.

## Example and validation

`examples/SessionRenewal.tet` creates a session, installs a five-minute
lease with NX, extends it to ten minutes with GT, and rejects a one-minute
renewal. Its main entry prints `600` on Node/Wasm, Bash and LuaJIT:

```sh
./tether exec examples/SessionRenewal.tet --host node
sh dev/m1-conditional-expiry.sh
```

Use the environment recorded in `TOOLCHAIN.md`. The ladder includes the
complete absolute-expiry ladder and pins these new checks:

- 875 store assertions covering condition tables, payload preservation,
  exact comparisons, nonzero clocks, deletion and overflow.
- 120 scenarios with 119 store and 120 LuaJIT checks, four additional
  clock scenarios, and eight atomic input refusals.
- 240 live Wasm/Bash executions checking replies, key presence, deadlines
  and retained payloads, plus the example on three hosts.
- 17 compiled source mutations, each required to fail its intended
  assertion, followed by ten restored controls.

The uncaught-error scenario runs in LuaJIT and both live hosts. The trusted
preludes total 164 lines. The existing trusted-line bounds remain unchanged:
Lua is 320/320 and the store is 200/200. The M0Spine checker and erasure use
51636 polls before a 12-poll static walk. Stage D gives that walk six polls
at fuel 51642 and still requires `SH-BUDGET` with no published output.

Other bulk Hash, List and Set operations, ZSet commands, the remaining
examples, the Lean exporter and M1 performance gates remain open.
