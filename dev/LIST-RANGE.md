# M1 List ranges

`lrange` reads a range of a List key and returns a typed `array` of `bulk`
replies. It takes erased result type `A` and tag `g`, then `Key List g`,
start `Signed64`, inclusive stop `Signed64`, and a `Reply -> Script A g`
continuation. Do-notation supplies the continuation.

Indices start at zero; negative indices count from the tail. Bounds clip
to the available elements. Missing keys, reversed ranges and ranges
outside the list return an empty array. Elements keep their order and
duplicates. Reads preserve the list and unrelated keys. These semantics
follow Redis's [LRANGE documentation](https://redis.io/docs/latest/commands/lrange/).

Both bounds use canonical decimal bytes over the full signed 64-bit
range. The Lua printer passes the bytes directly to Redis. The store
uses Int64 positions, and shares its inclusive range selection with
LTRIM. The independent LuaJIT twin bounds each decimal magnitude before
converting it. The surface rejects overflowing or noncanonical literals.
Defensive interpreter paths parse both bounds before checking key type,
including a missing or wrong-type key.

A wrong-type key returns a typed `err`. Scripts may inspect it; returning
it from an invocation stops the Client. LRANGE joins the read-only
allowlist and uses EVALSHA_RO with EVAL_RO fallback. A reachable write
in any case arm still requires write dispatch.

The Lua adapter constructs the existing `Reply` and `Replies` types so
Script code can inspect the array and its elements. Client replies retain
the whole array across later invocations. No reply constructor, host
protocol or foundation rule is added. Script command tag 27 is appended;
all existing tags keep their numbers.

Empty bytes, NUL, quotes, newlines, BOM, duplicate values and decimal-looking
strings remain bulk elements. The store and LuaJIT preserve arbitrary
bytes, including invalid UTF-8. The Node and REST text hosts reject an
array containing invalid UTF-8 with exit 4 and no stdout, while preserving
the list. Valid arrays print as compact JSON. Large replies remain
subject to the existing host and resource limits.

The LuaJIT CLI requests tagged replies from the independent twin and
formats them through the existing driver decoder. This distinguishes
arrays from bulk strings that happen to start with `array:[` and keeps
scalar replies, empty arrays and nested arrays intact.

```sh
dune build bin/tether.exe
./tether exec examples/QueuePreview.tet --host node
./tether exec examples/QueuePreview.tet --entry retained --host bash
./tether exec examples/QueuePreview.tet --entry retained --host luajit
sh dev/m1-list-range.sh
```

Both example entries print `["welcome:alice","welcome:bob"]`. The default
entry previews the first two jobs. `retained` returns that captured array
after trimming the queue to its last job. Each run owns an empty temporary
store. These examples do not provide a durable delivery protocol.

The two pinned preludes total 135 lines. Lua uses 320/320 lines and the
store uses 200/200. Sharing Set update handling preserves no-op behavior
and makes room for the array adapter within the existing store bound.
The Set mutation anchor follows that refactor and still requires the
duplicate-add assertion to fail. No source bound changes.
The bin group uses 404/450 lines, including the LuaJIT reply adapter in
the driver.

The gate runs the full List access ladder, then requires 101 unit cases,
18 artifact pairs, 18 typed refusals with no published output, 40 store
and 40 LuaJIT comparisons, eight LuaJIT CLI reply controls, 86 live host runs (82 with write EVAL commands
denied), two invalid UTF-8 refusals, two unhandled-error exits, six example
runs and eleven compiled mutants killed at their intended assertions. Five
controls pass before and after mutation. Arrays of 129 elements exercise
order and complete output. Failed builds skip dependent checks and make
the aggregate fail.

`python3 -P dev/list-range-tests.py --offline` omits listeners; `--static`
checks artifacts, refusals and interpreter examples; `--artifacts` checks
artifact pairs and write classification only; `--probe ENTRY` checks one
artifact and its LuaJIT cases for mutation controls. A flag run prints its
mode and a probe run prints its entry and case count, so no partial run can
satisfy the complete ladder's summary row.
Actual validation and timing results are recorded in `dev/M1-BUILD-LOG.md`.
