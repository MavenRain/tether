# M1 List commands

The List slice adds LPUSH, RPUSH, LPOP, RPOP and LLEN. The FIFO example
enqueues two mail jobs with RPUSH, drains them with LPOP and returns the
first captured reply after the second pop.

```sh
dune build bin/tether.exe
./tether exec examples/JobQueue.tet --host node
./tether exec examples/JobQueue.tet --host bash
./tether exec examples/JobQueue.tet --host luajit
./tether exec examples/JobQueue.tet --entry remaining --host node
./tether exec examples/JobQueue.tet --entry empty --host bash
```

The default entry prints `welcome:alice`, `remaining` prints `1`, and
`empty` prints a blank line for nil. Every `exec` owns an empty temporary
store. This example has destructive dequeue with no acknowledgement or
retry protocol; it demonstrates ordering, not durable job delivery.

Every constructor starts with erased result type `A` and tag `g`, and
ends with a `Reply -> Script A g` continuation supplied by do-notation.

| Constructor | Runtime operands | Successful reply |
| --- | --- | --- |
| `lpush` | `Key List g`, element `Bytes` | `int` new length after prepending |
| `rpush` | `Key List g`, element `Bytes` | `int` new length after appending |
| `lpop` | `Key List g` | `bulk` first element, or `nil` if missing |
| `rpop` | `Key List g` | `bulk` last element, or `nil` if missing |
| `llen` | `Key List g` | `int` length, zero if missing |

Pushes create missing lists and retain duplicate elements. Pops remove
one element and delete the key when it becomes empty. Empty bytes are
a bulk reply, distinct from nil. Wrong Redis types return a typed `err`
without changing the store. These semantics follow
[LPUSH](https://redis.io/docs/latest/commands/lpush/),
[RPUSH](https://redis.io/docs/latest/commands/rpush/),
[LPOP](https://redis.io/docs/latest/commands/lpop/),
[RPOP](https://redis.io/docs/latest/commands/rpop/) and
[LLEN](https://redis.io/docs/latest/commands/llen/).

Elements retain arbitrary bytes, including NUL, invalid UTF-8, quotes,
backslashes and newlines. The interpreter and LuaJIT can return all of
them. The existing Node and REST text hosts reject invalid UTF-8 replies
with exit 4 and no stdout. Valid UTF-8, NUL, BOM and trailing newlines
survive. A rejected pop reply does not undo the pop. Integers cross the
artifact boundary as decimal bulk strings using the existing count path.

LLEN joins the read-only allowlist and uses EVALSHA_RO and EVAL_RO.
Pushes and pops require write dispatch, including a pop in a reachable
case arm that is not taken. Scripts can inspect an `err`; returning it
from an invocation stops the Client. The type checker refuses List
commands on keys of another Redis type or tag.

The five prelude constructors append without changing existing tags.
At that slice the two preludes totaled 130 lines and the trusted counts
were Lua 315/320 and store 200/200. `SPEC.md` and `dev/LIST-ACCESS.md`
record current counts. The store shares empty
collection deletion among Hashes, Sets and Lists. Other trusted counts
and every bound are unchanged. The independent OCaml list uses linear
reversal for right-end operations; Redis supplies the production command
implementation. No new performance milestone is claimed here.

This slice accepts one element per push and one pop per command. List
range replies, bulk operations, blocking commands and reliable queue
protocols remain outside this slice. Indexed access, replacement and
trimming are documented in `dev/LIST-ACCESS.md`. `SPEC.md` lists the
remaining M1 work.

Run `sh dev/m1-lists.sh` with the toolchain in `dev/TOOLCHAIN.md`. It runs
the full Set ladder, List unit tests, artifact and type checks, OCaml and
LuaJIT comparisons, Wasm and Bash against temporary loopback Redis,
source mutants, the house audit and the trusted-line gate. The legs
`LISTS-UNIT-EXE` and `LISTS-TESTS-RUN` keep the suite rows, and the
`LISTS-COUNTS` leg requires the exact counts: 55 unit cases, 9 artifact
pairs, 32 refusals with 32 atomic outputs, 42 store and 42 LuaJIT
oracles, 42 live cases with 84 hosts, 10 read-only cases and 4 UTF-8
refusals, and 9 example runs. The suites require the same counts
themselves. A red `LISTS-BUILD` leg makes the dependent legs report
`SKIPPED` and `FAIL`, because a stale executable stays in `_build`.
Every other leg runs and a failing leg makes the final exit nonzero.

`python3 -P dev/lists-tests.py --offline` omits listeners. `--static`
checks artifacts, refusals and interpreter examples, and the mutation
runner uses it as a control before mutation; `--artifacts` is
the focused write-classification control used by the mutation runner.
Unit tests pin exact reply variants, both ends, remaining order, deletion
after the last pop, all five wrong Redis types, error propagation,
unchanged state on faults and unrelated keys on success. The LuaJIT and
live oracles compare every remaining element in order. Live LLEN cases
run with ordinary EVAL and EVALSHA denied. All three example entries
execute on Node, Bash and LuaJIT. Mutants cover direction, remainder
order, deletion, length, classification, nil and error reply tags, with
passing unit and offline controls before and after mutation.
