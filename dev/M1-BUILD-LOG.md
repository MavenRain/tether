# M1 build log

## 2026-09-11: do-notation

Base: `101f08e7b5a192d9f76055943367ce91f906e24e`, the user's committed
Stage F implementation and review fixes. This slice implements do-notation
over the existing Script and Client continuations. The new surface
expander recognizes block punctuation, preserves byte literals and
comments, and delegates ordinary tokens to the pinned lexer. Explicit
continuations remain supported. No kernel, prelude, printer, host, store,
trusted-line bound or frozen measurement changes.

`examples/DoCounter.tet` shows a counter, a Client selecting an earlier
reply after a second invocation, and an explicit fault after an effect.
Syntax and limits are documented in `dev/DO-NOTATION.md`.

Focused validation:

| Check | Result |
| --- | --- |
| Syntax and expansion | `PASS DO-SYNTAX legacy=20 expansion=8 refusals=20 locations=1` |
| Artifacts | `PASS DO-ARTIFACTS pairs=7 wasm=7 bash=7 lua=6 metadata=14 imports=1` |
| Checker and output cleanup | `PASS DO-CHECK refusals=8 first_order=1 atomic_output=9` |
| Host replies and stored effects | `PASS DO-HOSTS cases=7 luajit=5 effects=1` |
| Integration suite | `PASS DO-TESTS example=4` |
| Expander mutation controls | `PASS DO-MUTATIONS killed=4 survived=0 restored=1` |
| OCaml source audit | `PASS HOUSE`, zero findings across 27 files |
| Trusted lines | kernel 3997/4000, encoder 246/600, lua 283/320, sh 227/240, store 118/200, host-node 186/300, host-rest 156/300, bin 393/450 |

The seven artifact pairs compare every emitted file against independently
written explicit continuations. Runtime tests check both stdout and the
stored counter, so returning an earlier reply cannot conceal a dropped
command. The suite includes reply shadowing, nested blocks, punctuation
and NUL inside a byte literal, faults with and without preceding effects,
imported blocks, scope errors, type and tag errors, and the existing
first-order emission refusal. Failed programs must publish no directory.

The mutation tests change the actual expander in disposable trees. All
four mutants compile, fail the syntax suite with the marker recorded for
each one, and pass again after restoration. Rows are recorded in
`dev/MUTATION-LOG.md`.

Focused evidence under `/Users/oobi/Documents/gpt18/tether-m1-do/.kanon-exec/`:
`run-wZSKGI` (compiler and syntax-test build), `run-iFJqg9` (corrected
syntax-fixture build), `run-PtiBLl` (integration), and `run-WozCfU`
(source mutations), all exit 0.

The first baseline invocation ran inside the filesystem sandbox and failed
on localhost listener permissions (`listen EPERM`). Its capture is
`run-GkwWLC`; it is not a passing baseline. Subsequent host validation runs
with permission to start temporary loopback Redis and REST processes.

The committed baseline at `101f08e` passed `sh dev/stage-f.sh`, ending
with `PASS STAGE-F`, exit 0. Its production measurement was
`PASS M0-TIME median_ms=148.598 bound_ms=150`. The checkout remained clean
at the same commit afterward. Evidence: `run-9uAEOQ` in the capture
directory above. Stage A's separate mutation battery was not rerun.

The full candidate command `sh dev/m1-do.sh` passed, exit 0, in capture
`run-PigF0Q`. It ran the complete A through F ladder, the syntax and
artifact/host suites above, the new source mutants, and the final
house audit. Its last row is `PASS M1-DO`.

| Full-run measurement | Result |
| --- | --- |
| M0 compile time | median 134.154 ms, min 117.751 ms, max 175.223 ms, five runs |
| M0 timing gate | `PASS M0-TIME median_ms=134.154 bound_ms=150` |
| Frozen ratios | raw 20.622, corrected 32.741, end-to-end 4.802, informational |
| Fresh TinyCC | median 123.322 ms, empty 43.335 ms, raw ratio 23.430, span 2.105 s |
| Fixed cost | fixed 20.109 ms, per definition -0.055 ms, 100 added definitions, informational |
| Host load | 42.07, 52.65, 53.48 |

The timing gate uses the median; individual samples can exceed 150 ms.
Ratios and fixed-cost estimates retain their M0 informational status and
do not establish the M1 performance milestone. The inherited bounds and
frozen denominator files remain unchanged.

Remaining M1 work: the larger command surface, rate limiter, leaderboard,
job queue and session-store examples, EVALSHA_RO, the counted Lean 4
exporter, and M1 ratio and traversal gates. This slice does not declare
M1 complete or supply the user's M0-EXIT ratification.

### Review round 2026-09-11 (M1 do-notation)

Seven findings were ruled fix and all seven are applied in this round. The
eighth row, GATE-1, is the round-1 gate item, not one of the seven. No
bound moved, no pinned file changed, and `dev/M0-BUILD-LOG.md` is
untouched. This round does not grant M0-EXIT.

| id | Change |
| --- | --- |
| D-1 | `dev/m1-do.sh` now uses the `dev/gates.sh` leg wrapper. Every leg runs, each prints `PASS` or `FAIL`, and the script ends `PASS M1-DO` or `FAIL M1-DO` with a non-zero exit. |
| B-2 | `dev/do-mutations.py` carries one expected marker per mutant and adds FINAL-SEMI, which is killed by `FAIL DO-SYNTAX malformed do accepted:`. Result `PASS DO-MUTATIONS killed=4 survived=0 restored=1`. |
| C-1 | `dev/do-tests.py` now checks and runs `examples/DoCounter.tet` with the documented entries `main`, `earlier` and `stopped`, counted as `example=4` on the `PASS DO-TESTS` row. |
| A-1 | The block punctuation divergence is documented in `dev/DO-NOTATION.md` and pinned by four refusal cases in `dev/do_tests.ml`, so `refusals=20`. |
| B-4 | The DO-ARTIFACTS, DO-CHECK and DO-HOSTS counters are derived from the files and checks of the run instead of literal text. |
| B-5 | The `bad-command` refusal asserts `CHECK mismatch: the head of an application is not a function`. |
| C-3 | `SPEC.md` names the same remaining M1 work as this log, including the M1 ratio and traversal gates. |
| GATE-1 | The round 1 ladder did not pass. Both red legs are load artifacts: `FAIL STAGE-E` is the 120 second subprocess limit of one `dev/emit-lua.py` call at one minute load 75.78, and `FAIL M0-TIME median_ms=217.066 bound_ms=150` at load 94.88 is RED-LOAD. No source file, no gate and no recorded number changed; the rerun at load 25.98 ends `PASS M1-DO`, `EXIT-ALL 0`. |

Counter changes in this round: `refusals=16` becomes `refusals=20`,
`killed=3` becomes `killed=4`, the artifact counters become file counts
over the compared directories, `atomic_output` becomes the number of
refused programs proven to publish nothing, and `example=4` is new. No
timing number changed.

Round 2 of the same review read one gate finding, GATE-1: the round 1 gate
ladder ended `FAIL M1-DO` and `EXIT-ALL 1`. The log
`gates-gates-1.log` shows the one minute load at 75.78 when the run started
and at 94.88 when the timing leg ran. Two root causes make five red rows
there and both are
load artifacts, not code faults. `FAIL STAGE-E` comes from
`dev/stage-c-tests.py`, where the 120 second subprocess limit of one
`dev/emit-lua.py` call expired under that load. `FAIL M0-TIME
median_ms=217.066 bound_ms=150` is the documented RED-LOAD case, because the
recorded row of this slice is 134.154 ms (line 67) and a one minute load
above 40 moves it past the bound. Every DO leg passed in that same red log:
`PASS DO-SYNTAX legacy=20 expansion=8 refusals=20 locations=1`,
`PASS DO-ARTIFACTS pairs=7 wasm=7 bash=7 lua=6 metadata=14 imports=1`,
`PASS DO-CHECK refusals=8 first_order=1 atomic_output=9`,
`PASS DO-HOSTS cases=7 luajit=5 effects=1`, `PASS DO-TESTS example=4`,
`PASS DO-MUTATIONS killed=4 survived=0 restored=1`, and `PASS HOUSE`. The
Stage A battery in that run also passed: `PASS STAGE-A-MUTATIONS killed=37
survived=0 restored=1`. No source file,
no gate and no recorded number changed for GATE-1. No bound moved. The
same ladder was rerun at a lower load to settle the finding. The rerun
`gates-fix-2.log` started at one minute load 25.98 and measured the timing
leg at load 38.02, both under 40. It ends `PASS M0-TIME median_ms=64.310
bound_ms=150`, `PASS STAGE-F`, `PASS M1-DO`, `PASS STAGE-F-MUTATIONS
killed=3 survived=0 restored=2`, `PASS STAGE-A-MUTATIONS killed=37
survived=0 restored=1`, `EXIT 0`, `EXIT-MUT 0` and `EXIT-ALL 0`, with zero
`FAIL` rows and the same 13 porcelain rows before and after. GATE-1 is a
load artifact and needs no repair.

Refuted: 0 findings.

Merged and dropped: 5 findings. B-1 merged into D-1, same file
`dev/m1-do.sh:2` and the same defect, `set -eu` with no leg wrapper; D-1 is
the clearest statement and carries the `dev/gates.sh:6-18` contrast plus the
mutant reproduction. C-4 merged into D-1, the same defect stated from the
`dev/DO-NOTATION.md:65` side, its claim "prints no FAIL row at all"
corrected during verification because `dev/stage-f.sh` calls `dev/gates.sh`,
whose `leg()` prints `FAIL STAGE-F` first. B-3 merged into A-1, the same
defect, the bare `{`, `}`, `;` and `<-` class is both undocumented drift and
unexercised by the 20 legacy parity cases. C-2 merged into B-4, the same
defect from the `dev/M1-BUILD-LOG.md:22-24` side, while B-4 cites the source
of the constants. D-2 cut at the 7-finding cap as the weakest low, because
`dev/M1-BUILD-LOG.md:69` already reads informational and lines 74-75 already
state that fixed-cost estimates do not establish the M1 performance
milestone.

Gate block, last Workflow gates log `gates-gates-2.log`, verdict green, root
mode on the staged tree (the closing ladder gates-close.log is the last
paragraph of this block). One minute load 23.21 at the start row `19:09  up 25
days, 21:44, 27 users, load averages: 23.21 26.54 33.63`, 16.53 at the
timing leg row `LOAD 19:11  up 25 days, 21:46, 27 users, load averages:
16.53 21.97 30.55`, and 28.30 at the end row `19:12  up 25 days, 21:47, 27
users, load averages: 28.30 24.22 30.84`. Carry and count numbers:
`files=36 diff=0 vendor=32 copies=4`, `PIN 2c2e6e6 unlisted=0`, porcelain 13
rows before and 13 rows after. Mutation summary: DO-MUTATIONS killed=4
survived=0 restored=1, STAGE-F-MUTATIONS killed=3 survived=0 restored=2,
STAGE-A-MUTATIONS killed=37 survived=0 restored=1, STAGE-E-MUTATIONS
killed=15 restored=1, STAGE-E-INTEGRITY killed=14 restored=1,
STAGE-D-MUTATIONS killed=5 restored=1, STAGE-C-MUTATIONS killed=3
restored=1, STAGE-C-INTEGRITY killed=5 restored=1 and STAGE-B-MUTATIONS
killed=5 restored=1.

| leg line (verbatim) |
| --- |
| `LADDER tag=gates-2 mode=root leg=full root=/Users/oobi/Documents/tether start 19:09:16` |
| `PIN 2c2e6e6 unlisted=0` |
| `CARRY files=36 diff=0 vendor=32 copies=4` |
| `R0-COUNT formers=2 schema=4 shapes=5 admitted=3` |
| `R0-AUDIT ok` |
| `TRUSTED-LINES kernel=3997/4000 encoder=246/600 OK` |
| `PASS STAGE-A` |
| `PASS HOUSE` |
| `PASS STAGE-B-SURFACE cases=59` |
| `TRUSTED-LINES kernel=3997/4000 encoder=246/600 lua=283/320 sh=227/240 store=118/200 host-node=186/300 host-rest=156/300 bin=393/450 OK` |
| `PASS STAGE-B-MUTATIONS killed=5 restored=1` |
| `PASS STAGE-B` |
| `PASS STAGE-C-MUTATIONS killed=3 restored=1` |
| `PASS STAGE-C-TESTS` |
| `PASS STAGE-C-INTEGRITY killed=5 restored=1` |
| `PASS STAGE-C` |
| `PASS STAGE-D-MUTATIONS killed=5 restored=1` |
| `PASS STAGE-D-TESTS` |
| `PASS STAGE-D` |
| `PASS STORE-UNIT cases=25` |
| `PASS STAGE-E-INTEGRITY killed=14 restored=1` |
| `PASS STAGE-E-MUTATIONS killed=15 restored=1` |
| `PASS STAGE-E-TESTS cases=10` |
| `PASS STAGE-E` |
| `PASS DRIVER-BUILD` |
| `PASS DRIVER check=1 emit=1 run=1 exec=3 axioms=1 passes=1 refusals=5 disagreements=2` |
| `PASS M0-TIME-BOUNDARY below=149 at=150` |
| `PASS STAGE-F-MUTATIONS killed=3 survived=0 restored=2` |
| `PASS STAGE-F-TESTS` |
| `PASS CHECK definitions=29` |
| `PASS PASSES` |
| `LOAD 19:11  up 25 days, 21:46, 27 users, load averages: 16.53 21.97 30.55` |
| `BENCH m0-time median_ms=42.064 min_ms=40.818 max_ms=48.487 runs=5` |
| `PASS M0-TIME median_ms=42.064 bound_ms=150` |
| `PASS MEASURE` |
| `PASS TRUSTED-LINES` |
| `PASS STAGE-F` |
| `PASS DO-BUILD` |
| `PASS DO-SYNTAX legacy=20 expansion=8 refusals=20 locations=1` |
| `PASS DO-ARTIFACTS pairs=7 wasm=7 bash=7 lua=6 metadata=14 imports=1` |
| `PASS DO-CHECK refusals=8 first_order=1 atomic_output=9` |
| `PASS DO-HOSTS cases=7 luajit=5 effects=1` |
| `PASS DO-TESTS example=4` |
| `PASS DO-MUTATIONS killed=4 survived=0 restored=1` |
| `PASS M1-DO` |
| `EXIT 0` |
| `PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1` |
| `EXIT-MUT 0` |
| `EXIT-ALL 0` |

Zero `FAIL` rows in that log. This block does not grant M0-EXIT.

Fix rounds: 2.

Closing ladder: run tag close in root mode on the final staged tree
(13 paths, index equal to the worktree), gates-close.log in the review
work directory, 19:41:41 to 19:46:15, one-minute load 33.53 at the
start, 23.38 at the M0-TIME row and 19.22 at the end. Rows: PASS M1-DO,
PASS STAGE-F, PASS M0-TIME median_ms=36.330 bound_ms=150,
PASS DO-SYNTAX legacy=20 expansion=8 refusals=20 locations=1,
PASS DO-ARTIFACTS pairs=7 wasm=7 bash=7 lua=6 metadata=14 imports=1,
PASS DO-CHECK refusals=8 first_order=1 atomic_output=9,
PASS DO-HOSTS cases=7 luajit=5 effects=1, PASS DO-TESTS example=4,
KILLED REPLY-TYPE, ACTION-ORDER, LOST-TAIL and FINAL-SEMI by DO-SYNTAX,
PASS DO-MUTATIONS killed=4 survived=0 restored=1,
PASS STAGE-F-MUTATIONS killed=3 survived=0 restored=2,
PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1,
TRUSTED-LINES kernel=3997/4000 encoder=246/600 lua=283/320 sh=227/240 store=118/200 host-node=186/300 host-rest=156/300 bin=393/450 OK,
EXIT 0, EXIT-MUT 0, EXIT-ALL 0. FAIL rows: 0. Porcelain rows: 13 before
and 13 after. The slice is GREEN on the final tree.

### Read-only dispatch 2026-09-11

Baseline: `142ef37212261a5c2987b842ae8de57becf5cf1c`, the committed
do-notation slice and review fixes. Work was performed in
`/Users/oobi/Documents/gpt18/tether-m1-readonly` with the clean vendored
Kanon pin. The main Tether checkout was clean before this slice.

The existing no-writes classification now selects EVALSHA_RO and the
single EVAL_RO retry after NOSCRIPT. Bash uses the artifact field; Node
uses the canonical first line after verifying the Lua body hash. The
local REST allowlist admits both commands. Mixed Clients select mode per
script and preserve captured replies. No kernel, prelude, ABI, frozen
denominator, or trusted-line bound changed.

Focused evidence, under the work directory's `.kanon-exec`:

| Artifact | Result |
| --- | --- |
| `run-CwFowf` | Driver, shell emitter, Lua emitter and store runner built successfully. |
| `run-8NCCzl` | All four read-only host tests passed through kanoncho. |
| `run-g5cBAu` | RO-SH, RO-LIVE, RO-E2E and RO-TESTS passed. |
| `run-cLciPj` | Four dispatch mutants killed; both restored suites passed. |

RO-E2E covered twelve actual Wasm/Bash executions against a temporary
Redis whose ACL refused ordinary EVAL and EVALSHA. It compared missing
keys and exact signed decimal strings against six independent store
runs and six LuaJIT runs. Two mixed executions returned the earlier reply
and verified the final stored value. RO-LIVE flushed the script cache for
both hosts, compared fallback bodies and keys, and confirmed that Redis
refused a write from a no-writes script without changing the key.

Two test-harness corrections preceded the green focused runs. The initial
artifact check expected Stage D's separate Wasm carriers; it now uses the
existing full Client Wasm byte comparison. The first mutation run caught
the mutant but could not match the default Node reporter; the runner now
pins TAP and requires its named failed-test line. These corrections did
not change production behavior or weaken a gate.

The build used OCaml switch `zxcaml-p1`, clearing OPAM_SWITCH_PREFIX,
CAML_LD_LIBRARY_PATH, OCAMLPATH and OCAMLFIND_CONF. Local integration used
Redis 8.10.1. Syntax, diff whitespace and the OCaml house audit passed.
Trusted lines: kernel 3997/4000, encoder 246/600, lua 283/320, sh 227/240,
store 118/200, host-node 196/300, host-rest 156/300, bin 393/450.

Remaining M1 work includes the wider command surface, rate limiter,
leaderboard, job queue, session store, counted Lean exporter, and the M1
performance and traversal gates. This slice does not declare M1 complete.

The first full `sh dev/m1-readonly.sh` run, `.kanon-exec/run-DfkO2z`,
exited 1. Two root failures propagated through the ladder: Stage C's
LuaCases.binary emitter exceeded its unchanged 120-second deadline, and
M0-TIME measured 198.098 ms against the unchanged 150 ms bound. Observed
one-minute load was 121.31 after the timeout and 86.84 at the timing row.
Stage A, Stage B and its mutations, the Stage F driver/integration and
mutation tests, every DO leg, and every RO leg passed. The Stage C timeout
prevented Stage D and E's remaining tests from running in that attempt.
No production source, deadline, or measurement bound changed for the rerun.

The complete unchanged ladder then passed in `.kanon-exec/run-MGSS6s`,
exit 0, ending `PASS M1-READONLY`. Stages A through F, the do-notation
ladder, all read-only tests and all included mutation suites passed.
M0-TIME measured 43.540 ms against the 150 ms bound. The RO rows were
`PASS RO-SH fallback=2 mixed=1 faults=4`,
`PASS RO-LIVE node_flush=1 bash_flush=1 write_refused=1 exact_bytes=1`,
`PASS RO-E2E acl_readonly=12 mixed=2 store=6 luajit=6`, and
`PASS RO-MUTATIONS killed=4 survived=0 restored=2`.
Trusted-line counts remained those reported above. The standalone Stage A
37-case mutation battery was not rerun; its production inputs were unchanged.

### Review round 2026-09-11 (M1 read-only dispatch)

The review of this slice kept seven findings. All seven are fixed here.
No bound moved, no frozen record changed and no measurement was invented.

| id | Site | Change |
| --- | --- | --- |
| A-1 | `dev/readonly-tests.py` | A second ACL control requires NOPERM for `EVALSHA`, so the read-only ACL now polices the suffix both hosts actually send. |
| B-1 | `dev/readonly-tests.py` | The RO-SH row reports counted transcripts instead of three literals. |
| B-2 | `dev/readonly-tests.py` | The RO-E2E row reports counted store runs, counted LuaJIT runs and counted mixed executions beside the counted ACL executions. |
| B-3 | `dev/readonly-tests.py` | The RO-LIVE row is the child verdict line, re-emitted verbatim, instead of a literal copy. |
| B-4 | `dev/readonly-tests.py` | Each Node execution compares Redis `INFO commandstats` before and after, and requires one `SCRIPT LOAD`, the expected number of `EVALSHA_RO` calls and no `EVAL`, `EVALSHA` or `EVAL_RO`. |
| C-1 | `dev/MUTATION-LOG.md` | The restored-suite sentence now names the shell-only transcript suite and records that the runner never reruns RO-LIVE or RO-E2E. |
| A-3 | `runtime/redis-host.mjs` | The Node host parses the shebang flag list instead of comparing 22 fixed bytes, and a new host case derives both header branches from `print/lua.ml` and requires the Node classifier to agree. |

The counted values equal the documented ones, so `PASS RO-SH
fallback=2 mixed=1 faults=4`, `PASS RO-E2E acl_readonly=12 mixed=2
store=6 luajit=6` and `PASS RO-LIVE node_flush=1 bash_flush=1
write_refused=1 exact_bytes=1` are unchanged rows with earned numbers.

Two recorded quantities moved. Trusted lines for the Node host rose from
188/300 to 196/300 with the flag parser, and the paragraph above carries
the new count. The host suite holds five cases instead of four; the
evidence row for `run-8NCCzl` keeps its own count because it records what
that earlier run executed.

Each fix was proved on a copy through the copy-mode ladder queue with the
`ro-tests` leg. `gates-fix-1-c2.log` is the clean copy. `gates-fix-1-m1b.log`
weakens the ACL setup to `-eval` alone and the new control fails.
`gates-fix-1-m2b.log` deletes one fault transcript, one initial store value
and zeroes the child RO-LIVE counts, and the three rows follow the deletions
instead of printing the old literals. `gates-fix-1-m3b.log` makes the Node
host send `EVAL_RO` on every invocation and the new command-counter check
fails, where the old leg passed. The first copies (`gates-fix-1-c1.log`,
`-m1`, `-m2` and `-m3`) are void because they lacked the built store runner;
the reruns above used rebuilt copies. The root ladder of the round is
`gates-fix-1.log`.

Refuted: 0. No verifier refuted a finding this round.

Merged and dropped: 9. B-5 merged into A-1 (same file, same line
`dev/readonly-tests.py:72`, same defect: the ACL control probes EVAL
only). C-4 merged into D-1 (same defect: `dev/READONLY.md:36-39` does
not record that the M1-DO leg reruns the lower ladder, so verdict rows
repeat in a green log). Seven low items fell to the seven cap: D-1 (the
duplicate TRUSTED-LINES leg at `dev/m1-readonly.sh:16` asserts the same
unchanged tree as `dev/gates.sh:17`), A-2 (the mixed entry runs after
the ACL restore at `:98`, so only the live proof of per-script dispatch
is missing; it overlaps B-4), A-4 (no socket-free test pins the REST log
record for the new names), B-6 (NODE-MODE and NODE-FALLBACK share one
kill marker, and both mutants still die, so `killed=4` is true), B-7 (no
SH-FALLBACK mutant covers `EVAL$suffix` at `print/sh.ml:107`; adding one
moves the killed count and the MUTATION-LOG table), C-2 (`README.md:10-12`
does not say the default `examples/ReadOnly.tet` entry prints an empty
line, which `dev/READONLY.md:32` already records) and C-3
(`README.md:33` says the counter commands above print 1, which is false
for the check, emit and stage-f rows of the block at `:20-29`).

Gate of record: `gates-gates-1.log`, tag `gates-1`, root mode on
`/Users/oobi/Documents/tether`, 22:58:09 to 23:16:28, zero FAIL rows,
17 porcelain rows before and after. One-minute load 33.12 at the start,
35.54 at the MEASURE leg, 39.29 at the end of the ladder and 31.84 at
the close. Carry and counts: `PIN 2c2e6e6 unlisted=0`, `CARRY files=36
diff=0 vendor=32 copies=4`, `R0-COUNT formers=2 schema=4 shapes=5
admitted=3`, `TRUSTED-LINES kernel=3997/4000 encoder=246/600 lua=283/320
sh=227/240 store=118/200 host-node=196/300 host-rest=156/300 bin=393/450
OK`, `DO-SYNTAX legacy=20 expansion=8 refusals=20 locations=1`,
`DO-ARTIFACTS pairs=7`, `DO-CHECK refusals=8`, `DO-HOSTS cases=7`,
`STORE-UNIT cases=25`, `STAGE-E-TESTS cases=10`, `LOAD-ONCE
rest_calls=1 invoke_lines=1 warmup_calls=2`, `M0-TIME median_ms=119.178
bound_ms=150`.

| Leg | Verbatim row |
| --- | --- |
| STAGE-A | `PASS STAGE-A` |
| HOUSE | `PASS HOUSE` |
| STAGE-B | `PASS STAGE-B` |
| STAGE-C | `PASS STAGE-C` |
| STAGE-D | `PASS STAGE-D` |
| STAGE-E | `PASS STAGE-E` |
| MEASURE | `PASS M0-TIME median_ms=119.178 bound_ms=150` and `PASS MEASURE` |
| STAGE-F | `PASS STAGE-F` |
| M1-DO | `PASS M1-DO` |
| RO-HOSTS | `PASS RO-HOSTS` (node tests 5, pass 5, fail 0) |
| RO-TESTS | `PASS RO-SH fallback=2 mixed=1 faults=4`, `PASS RO-LIVE node_flush=1 bash_flush=1 write_refused=1 exact_bytes=1`, `PASS RO-E2E acl_readonly=12 mixed=2 store=6 luajit=6`, `PASS RO-TESTS` |
| RO-MUTATIONS | `PASS RO-MUTATIONS killed=4 survived=0 restored=2` |
| TRUSTED-LINES | `TRUSTED-LINES kernel=3997/4000 encoder=246/600 lua=283/320 sh=227/240 store=118/200 host-node=196/300 host-rest=156/300 bin=393/450 OK` and `PASS TRUSTED-LINES` |
| ladder | `PASS M1-READONLY`, `EXIT 0` |
| Stage A battery | `PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1`, `EXIT-MUT 0` |
| run | `EXIT-ALL 0` |

Mutation summary of that log: RO-MUTATIONS killed=4 survived=0
restored=2, DO-MUTATIONS killed=4 survived=0 restored=1,
STAGE-F-MUTATIONS killed=3 survived=0 restored=2, STAGE-E-MUTATIONS
killed=15 restored=1, STAGE-E-INTEGRITY killed=14 restored=1,
STAGE-D-MUTATIONS killed=5 restored=1, STAGE-C-MUTATIONS killed=3
restored=1, STAGE-C-INTEGRITY killed=5 restored=1, STAGE-B-MUTATIONS
killed=5 restored=1 and STAGE-A-MUTATIONS killed=37 survived=0
restored=1.

Fix rounds: 1.

Closing ladder: `gates-close.log`, tag `close`, root mode, 23:31:11 to
23:38:25 at one-minute load 13.77 to 15.74, zero FAIL rows, porcelain 17
and 17 rows before and after. Rows: `PASS M1-READONLY`, `PASS M1-DO`,
`PASS STAGE-F`, `PASS M0-TIME median_ms=73.713 bound_ms=150`, `PASS
RO-HOSTS`, `PASS RO-SH fallback=2 mixed=1 faults=4`, `PASS RO-LIVE
node_flush=1 bash_flush=1 write_refused=1 exact_bytes=1`, `PASS RO-E2E
acl_readonly=12 mixed=2 store=6 luajit=6`, `PASS RO-TESTS`, `PASS
RO-MUTATIONS killed=4 survived=0 restored=2`, `PASS STAGE-A-MUTATIONS
killed=37 survived=0 restored=1`, `TRUSTED-LINES kernel=3997/4000
encoder=246/600 lua=283/320 sh=227/240 store=118/200 host-node=196/300
host-rest=156/300 bin=393/450 OK`, `EXIT 0`, `EXIT-MUT 0`, `EXIT-ALL 0`.
The counted rows and the trusted-line counts equal those of the gate of
record above.
