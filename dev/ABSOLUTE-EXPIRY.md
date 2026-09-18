# M1 absolute expiry

The new constructors share each key's erased Redis type and tag:

| Constructor | Arguments after `Reply` | Script tag |
| --- | --- | --- |
| `expireat` | `t g key timestamp` | 44 |
| `pexpireat` | `t g key timestamp` | 45 |
| `expiretime` | `t g key` | 46 |
| `pexpiretime` | `t g key` | 47 |

Each ends with a `Reply -> Script Reply g` continuation, supplied by
do-notation. Keys have type `Key t g` and timestamps have type `Signed64`.
All seven key types are accepted. Incorrect types, tags and noncanonical
or overflowing literals are refused before output publication.

EXPIREAT takes Unix seconds and PEXPIREAT takes Unix milliseconds.
Both return integer `1` for an existing key and `0` for a missing key.
A deadline at or before the current clock deletes an existing key.
Seconds-to-milliseconds overflow is checked even for missing keys and
returns `ERR invalid expire time in 'expireat' command`.
These rules follow [EXPIREAT](https://redis.io/docs/latest/commands/expireat/)
and [PEXPIREAT](https://redis.io/docs/latest/commands/pexpireat/).

EXPIRETIME and PEXPIRETIME return the absolute deadline in seconds or
milliseconds. A persistent key returns `-1` and a missing key returns
`-2`, as specified by [EXPIRETIME](https://redis.io/docs/latest/commands/expiretime/)
and [PEXPIRETIME](https://redis.io/docs/latest/commands/pexpiretime/).
Redis 8.10.1 rounds seconds to the nearest integer with half seconds up,
using its [shared TTL implementation](https://github.com/redis/redis/blob/8.10.1/src/expire.c#L791-L831).
The store and independent LuaJIT twin use the same rounding.

Timestamp arguments travel as exact decimal strings. Replies use the
existing expiry range guard: only integers from `-2` through
`9007199254740991` are accepted. Larger replies, fractions and incorrect
reply shapes produce `ERR expiry reply is outside exact integer range`.
An accepted deadline can exceed that reply limit. An error reading it
leaves the previously installed deadline intact. Errors remain catchable
Script replies; an uncaught error stops subsequent Client invocations.

EXPIRETIME and PEXPIRETIME use read-only dispatch. The two setters use
write dispatch. Wasm and Bash carry identical canonical Lua bodies and
declare each key once.

## Clocks and interoperability

Absolute setters use the timestamp directly without adding the clock.
Absolute readers return the stored timestamp without subtracting it.
Relative expiry, absolute expiry and PERSIST share the same deadline map.
Advancing the store clock leaves absolute replies unchanged until expiry.
At an existing deadline the key is still visible; one millisecond later
it is removed, following the lookup rule described in `TTL.md`.

`Store.empty` and normal LuaJIT execution start at clock zero. The store
runner accepts an optional initial millisecond clock for deterministic
checks. Live hosts use Redis's clock. A positive timestamp in the past
can therefore behave differently in a zero-clock interpreter and a live
host. The cross-host fixtures use deadlines in 2100 or nonpositive
timestamps; controlled clocks separately cover positive past deadlines.

`examples/SessionDeadline.tet` installs a deadline of `4102444800` Unix
seconds (2100-01-01 UTC) and reads it back. SET clears that deadline,
PERSIST removes it, and in-place edits preserve it as documented in `TTL.md`.

## Validation and remaining work

Run `sh dev/m1-absolute-expiry.sh` with `dev/TOOLCHAIN.md`'s environment.
The ladder includes the full TTL ladder, 162 store assertions, 38 scenarios
on 37 interpreter and 38 LuaJIT oracles, six clock scenarios with three
additional interpreter checks, six atomic input refusals, 76 live
Wasm/Bash executions, and the example on three hosts. The uncaught-error
scenario is tested in LuaJIT and both live hosts. Fourteen mutations must
fail their intended assertions, followed by eight restored controls.

At that slice the four constructors brought the trusted preludes to 154
lines. `SPEC.md` records the current count.
Checker/erasure cost for M0Spine was 44256 polls at this slice and its
static walk was 12 polls. Stage D supplied six walk polls at fuel 44262
to retain its printer-budget refusal. Lua remains 320/320 and store 200/200;
no trusted-line limit or timing bound changes.

Conditional expiry, atomic SET-with-expiry options, the full session-store
example and the other outstanding M1 milestones remain pending.
