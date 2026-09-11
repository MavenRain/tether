# tether specification

Stage F implementation, 2026-09-11. The driver emits the executable Wasm
Client and Bash pair. The foundation, counter surface, printers, store and
local hosts are implemented. See `dev/STAGE-B.md` through `dev/STAGE-F.md`
for syntax and limits. The latest build-log entry records whether the
independent M0 timing gate has passed; this text does not stamp M0-EXIT.

## Foundation (inherited)

The sole primitive formers are `Lan` and `Ran`. The kernel, surface checker
and WasmGC emitter come from `vendor/kanon` at
`2c2e6e6831a0b2cf3107fa4aad392606109a2bcf`, recorded in `dev/PIN`.
The full inherited grammar and checking rules are in `vendor/kanon/SPEC.md`.
All source citations below are relative to that submodule at the pin.
M0 adds zero kernel lines and zero patches. `dev/PATCHES/.gitkeep` is empty.

Script, Client and folds are namings, not additional Kan formers.
`mu_pack` assembles the mu rule fields and refuses the right former
(`lib/rules.ml:1388`). The colimit along `! : omega -> 1` is constructed in
the metatheory record `dev/INITIAL-CHAIN.md` of the pin.
This does not admit a codensity construction:

- `Ran_U U` is refused: `lib/rules.ml:952` and `lib/rules.ml:1083-1086`.
- Nested `Op (Script A)` is refused: `lib/positivity.ml:85-90`.
- `SPar` is refused: `lib/rules.ml:1429`.
- `SNu` is refused: `lib/rules.ml:1432`.

## R0 counts

Inherited verbatim from the pin's specification. `dev/r0-count.sh` builds
the vendored driver and compares its derived counts against this block
and the committed upstream block.

```
formers 2: Lan Ran
schema constructors 4: In Elim Sec Out
shapes declared 5: SPi SColl SPar SMu SNu
shapes admitted 3: SPi SColl SMu
named rules declared 3: proof-irrelevance subsingleton-large-elimination literal-fast-path
named rules present 3: proof-irrelevance subsingleton-large-elimination literal-fast-path
eta rows 3: Ran-SPi Lan-SPi Ran-SColl
no eta 3: Lan-SColl Ran-SMu Lan-SMu
```

## M0 surface contract

Source files end in `.tet`. Module paths use dotted PascalCase and match
the path under the source root: `Data.Reply` lives in `Data/Reply.tet`.
The two tiers elaborate into the inherited kernel:

- `Script A` is an inline strictly positive `SMu`, with `pure` and one
  constructor per admitted command. Recursive continuations stand to the
  right of arrows. Data-dependent loops belong to this tier.
- `Client A` has `done`, `inv` and `fail : Fault -> Client A`. `Fault`
  uses `Lan (SColl 6)` for Noscript, Busy, Oom, Network, Http and Discarded.
  Bash emission refuses higher-order client control by name.
- `Reply` and `Replies` form a mutual `SMu` group, with nil, int, bulk,
  status, err and array variants. The inherited mutual surface is at
  `SPEC.md:344` in the submodule.
- `Key t g` is an indexed `SMu`. A separate quantity-zero `Tag` is shared
  by the keys of one script. An index is nonempty and contains neither
  `{` nor `}`. Cross-slot schemas print `allow-cross-slot-keys`.

The M0 program is one counter script performing INCR then GET on one key.
Integers that can exceed 2^53 cross both artifact boundaries as bulk
strings, including the fixture `9007199254740993`. Int64 is a refinement
in the types. No numeric conversion may silently replace this string.

## Artifact contract

`tether emit FILE -o DIR` writes `prog.wasm` and `prog.sh`. Both carry
identical canonical Lua bodies without a trailing newline. The WasmGC
module is import-free and uses the carried reactor with invoke code 10
and result-formatting code 11. Its compiled state retains the selected
reply across subsequent calls and terminates on the first host fault.
`runtime/reactor.kan` is byte identical to the pin. The Node host runs
RESP2 against Redis. The REST twin has its own decoder in a separate file.

Both artifacts SCRIPT LOAD on first use, EVALSHA thereafter, and EVAL on
NOSCRIPT. Steady state makes one REST request per invoke line. Bash 3.2
uses `set -eu`, quoted expansions, quoted heredocs and `jq -n --args`
for request bodies. Reply variants are inspected before payload extraction;
every emitted `case` has a `*) exit 4` arm. Equality compares stdout text.
Lua is 5.1, deterministic, uses local bindings, and takes KEYS and ARGV as
inputs. The independent Lua twin runs under `luajit -joff` and a strict
global metatable.

## Bounds and milestone limits

Inherited trusted lines: kernel 3997/4000 and encoder 246/600. Stage F
measures lua 283/320, including flags, SHA-1 and byte lowering; sh 227/240,
including the shared Client plan and reactor printer; store 118/200;
host-node 186/300; host-rest 156/300; and bin 393/450, covering the command
host, the driver and the local process owner. Both trusted preludes are pinned by
`dev/PRELUDES.sha256`; their 109 lines are reported separately without
adding or changing a ruled bound.
The store and printers live outside `lib`.
OCaml uses explicit Result/Option errors, exhaustive sum matches and total
combinators, with no exceptions, partial indexing or imperative loops.

M0 measures parse through both artifacts on disk, excluding wasm-opt,
SCRIPT LOAD and hosts. The M0-TIME bound is strictly under 150 ms;
the TinyCC ratios and PASSES are informational. Stage 0's denominators
and hashes remain frozen; a fresh TinyCC spine sample prints separately.
Stage F compares exact stdout from the executable Wasm Client, Bash and
LuaJIT, including large integers and captured replies. `--passes` counts
the three observed surface declaration passes and does not instrument
internal kernel traversals. `dev/stage-f.sh` returns failure if the
compile-time median exceeds its bound, even when all functional gates pass.

M1 adds the larger command surface, do-notation, EVALSHA_RO and a counted
Lean 4 exporter. M2 adds migrations, batch, PUBLISH and parity gates.
M3 adds universes, quotients, coinduction, a wasmtime host, RESP3, Streams
and Redis Functions. Nested inductives are NEVER, using the mutual form
as their encoding. Typeclasses and instance search are NEVER at M0 to M2.
Live Upstash with a user-exported token is M4. Earlier gates use localhost.

## Stage A validation

Run `sh dev/stage-a.sh`. PIN checks the ruled hash, submodule HEAD and
staged gitlink. CARRY compares the complete lib/wasm/runtime inventory and
four copied files against submodule commit objects. It also compares the
submodule worktree against the file list of the pin, so an added
file under any directory the scoped build compiles fails the gate. A
nested gitlink of the pin has three legs of its own: the directory must
exist, an initialized checkout must sit at the pinned head, and an
uninitialized checkout must hold no file. An initialized nested checkout
is compared against its own pinned head, so a changed tracked file and an
added file inside it both fail the gate. No gate
reads the origin checkout. R0-COUNT compares all eight derived rows and
prints the counts it read. R0-AUDIT joins the whole prose surface of this
file into sentences, across blank lines, list markers and table lines. A
sentence counts as a claim when it links a subject to a naming, refusal,
admission or permission word, with a copula or with one of the state verbs
stay, remain, become and continue, or when it grants a nesting permission.
Every claim sentence must be a ruled one with an audited citation. The
audit also checks the refusal sites and runs the inherited shape isolation
script under a working ripgrep. The inherited trusted-line check, its printed line and
eight frozen checksum entries must also pass.

`python3 -P dev/stage-a-mutations.py` exercises failures on temporary copies.
The mutation log records the cases and the build log records validation.
