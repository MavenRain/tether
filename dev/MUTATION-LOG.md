# M0 mutation log

## Stage 0

Date: 2026-09-09.  Every mutant ran on a copy under /Users/oobi/Documents/tether-m0/mutants/ and never on a repository file.  Each copy was deleted after its run, and the sha256 of each original was printed before and after the three runs.  Runner: /Users/oobi/Documents/tether-m0/judge/mutants.sh;  transcript: /Users/oobi/Documents/tether-m0/judge/mutants.log.

Originals before and after, both prints equal:

```
736a6c465142bec4a3fd985a6f9d23ccb06ddce842774585af22fe473604a5a4  dev/DENOMINATORS.sha256
9eb4415dc3a730e89742f13535413cceb77671f21420c9137a4bebbc5d99d6e5  corpus/lua/m0-spine.lua
789550fa6cb8641e4adbdc0b5ae8a1aaabf4bf067f4ab6b3e0436cec97d4d6c1  /Users/oobi/Documents/tether-m0/spikes/pin/PIN
```

The PIN file still holds 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf, and `fd -H -t f .` over the mutant directory counts 0 files after the last run.

### S0-M1 hash, KILLED

Mutation: one hex digit of the dev/bench.sh row of dev/DENOMINATORS.sha256, `d408fb5a` to `e408fb5a`, in the copy.

```
sd 'd408fb5a' 'e408fb5a' < /Users/oobi/Documents/tether/dev/DENOMINATORS.sha256 > /Users/oobi/Documents/tether-m0/mutants/DENOMINATORS.sha256.mut
zsh -c "cd /Users/oobi/Documents/tether && shasum -a 256 -c /Users/oobi/Documents/tether-m0/mutants/DENOMINATORS.sha256.mut"
```

Output:

```
dev/bench.sh: FAILED
dev/denominators.json: OK
dev/tcc-denominator.sh: OK
corpus/twin/spine.c: OK
corpus/twin/sort.c: OK
corpus/twin/parser.c: OK
corpus/twin/interp.c: OK
corpus/lua/m0-spine.lua: OK
shasum: WARNING: 1 computed checksum did NOT match
```

Exit code 1.  The check prints FAILED on the mutated row only and exits non-zero, so the mutant is killed.

### S0-M2 body, KILLED

Mutation: one newline appended to a copy of corpus/lua/m0-spine.lua, 71 bytes to 72 bytes.

```
cp /Users/oobi/Documents/tether/corpus/lua/m0-spine.lua /Users/oobi/Documents/tether-m0/mutants/m0-spine.lua.mut
printf '\n' >> /Users/oobi/Documents/tether-m0/mutants/m0-spine.lua.mut
zsh /Users/oobi/Documents/tether/dev/spike-body.sh /Users/oobi/Documents/tether-m0/mutants/m0-spine.lua.mut
```

Output:

```
BODY-DIFF sha256_heredoc=9eb4415dc3a730e89742f13535413cceb77671f21420c9137a4bebbc5d99d6e5 sha256_file=38b0011fcd3cc16bfb7760e8f4b023553a3a164c4bf4dd6ba6715128e5bcf026
```

Exit code 1.  The quoted heredoc drops the added newline, so the extracted body keeps the canonical hash while the file hash moves, the script prints BODY-DIFF and the mutant is killed.

### S0-M3 pin, KILLED

Mutation: two characters of the sha transposed in a copy of the scratch PIN file, `2c2e` to `c22e`.

```
sd '^2c2e' 'c22e' < /Users/oobi/Documents/tether-m0/spikes/pin/PIN > /Users/oobi/Documents/tether-m0/mutants/PIN.mut
zsh /Users/oobi/Documents/tether/dev/spike-pin.sh /Users/oobi/Documents/tether-m0/spikes/pin /Users/oobi/Documents/tether-m0/mutants/PIN.mut
```

Output:

```
PIN FAIL submodule HEAD 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf differs from PIN c22e6e6831a0b2cf3107fa4aad392606109a2bcf
```

Exit code 1.  The first of the three sha comparisons fails, the script prints PIN FAIL and the mutant is killed.

### Result

Three mutants, three killed, none survived.

## Stage A (2026-09-09)

Runner: `python3 -P dev/stage-a-mutations.py`. Each mutation runs in a
temporary copy with its own Git metadata. Baseline and restored controls
pass. Every mutant exits 1 from its expected gate, and the runner exits 0.

The runner reads the printed reason of every case. An exit code and the leg
name alone do not score a kill, so an environment fault cannot pass for a
caught mutant. A case whose gate calls an inherited script requires the text
that script prints over the mutated file, so a missing or broken script
scores no kill. The reason column below is the text the runner requires.

| Case | Mutation | Caught by |
| --- | --- | --- |
| PIN-BYTE | Change the first character of dev/PIN from 2 to 3. | CARRY: dev/PIN differs from ratified pin. |
| VENDOR-BYTE | Append a newline to vendor runtime/run.mjs. | CARRY: tracked vendor file differs from pin: ['runtime/run.mjs']. |
| COPY-BYTE | Append a newline to the copied runtime/reactor.kan. | CARRY: carried bytes differ: runtime/reactor.kan. |
| MISSING-FILE | Remove vendor wasm/emit.ml. | CARRY: tracked vendor file differs from pin: ['wasm/emit.ml']. |
| IGNORED-EXTRA | Add lib/extra.o, untracked at the pin. | CARRY: carried inventory differs: ['lib/extra.o']. |
| SURFACE-EXTRA | Add surface/extra.ml, a module the scoped build compiles. | CARRY: files in the submodule worktree are not listed by the pin: ['surface/extra.ml']. |
| NAMED-PATCH | Add dev/PATCHES/unruled.patch. | CARRY: M0 requires zero named patches. |
| R0-ROW | Change the SPEC former count from 2 to 3. | COUNT: SPEC counts differ from inherited block. |
| REFUSAL-CITATION | Change the mu refusal citation from line 952 to 953. | AUDIT: refusal citation is not an audited site. |
| ANCHOR-MOVED | Change the text of the anchored line lib/rules.ml:952 in the submodule. | AUDIT: refusal site moved: lib/rules.ml:952. |
| UNCITED-NAMING | Append a naming sentence with no refusal citation to SPEC.md, wrapped over two lines as the file wraps. | AUDIT: naming or refusal statements differ from the ruling: ['Key and Tag are namings, not additional Kan formers.']. |
| BLANK-WRAP-NAMING | Append the same naming sentence wrapped over a blank line. | AUDIT: naming or refusal statements differ from the ruling: ['Key and Tag are namings, not additional Kan formers.']. |
| LIST-WRAP-NAMING | Append a permission sentence wrapped over two list items. | AUDIT: naming or refusal statements differ from the ruling: ['`SNu` is allowed after M0 and']. |
| REPHRASED-ADMISSION | Append an admission that uses none of the ruled phrases. | AUDIT: naming or refusal statements differ from the ruling: ['`SPar` is accepted at M0.']. |
| SHAPE-LEAK | Add a shape name in a comment in lib/eval.ml. | AUDIT: inherited shape isolation audit failed, plus the leaking line `lib/eval.ml:` and the line `R0-AUDIT FAIL` of the inherited script. |
| NO-RG | Put an rg that exits 127 first on PATH, with no source mutation. | AUDIT: rg is on PATH but exits 127. |
| GITLINK | Change the staged submodule hash while leaving its HEAD at the pin. | CARRY: staged gitlink differs from pin. |
| HEAD-SHA | Move the submodule HEAD ref to the parent commit, leaving every worktree file at the pin. | CARRY: submodule HEAD differs from pin. |
| SIXTH-SHAPE | Add SExtra to Shape.declared and run r0-count.sh. | COUNT: the rebuilt executable prints shapes declared 6. |
| DENOMINATOR-BYTE | Append a newline to the frozen dev/tcc-denominator.sh and run stage-a.sh. | sha256: dev/tcc-denominator.sh: FAILED. |
| NO-AWK | Put an awk that exits 127 first on PATH and run stage-a.sh. | TRUSTED-LINES FAIL unexpected line. |
| NONCOPULA-REFUSAL | Append a refusal that uses the state verb stays instead of the copula, with no citation. | AUDIT: refusal with no citation: `SPar` stays refused after M0. |
| UNTOKENED-NAMING | Append a naming of two names that no ruled row mentions. | AUDIT: naming or refusal statements differ from the ruling: ['Key and Tag are namings.']. |
| NESTED-MISSING | Move the nested checkout vendor/kanon/vendor/tot aside. | CARRY: nested submodule directory missing: vendor/tot. |
| NESTED-HEAD | Initialize the nested checkout vendor/kanon/vendor/tot at a commit of its own. | CARRY: nested submodule HEAD differs from pin: vendor/tot. |
| NESTED-EXTRA | Add lib/tot.ml in the uninitialized nested checkout vendor/kanon/vendor/tot. | CARRY: nested submodule directory is not empty: vendor/tot. |
| NESTED-UNLISTED | Add extra_leak.ml in the nested checkout vendor/kanon/vendor/tot, initialized at the pinned head. | CARRY: files in the nested submodule are not listed by the pin: ['vendor/tot/extra_leak.ml']. |
| NESTED-TRACKED | Append a newline to dune-project in the initialized nested checkout vendor/kanon/vendor/tot. | CARRY: tracked file in the nested submodule differs from pin: ['vendor/tot/dune-project']. |
| NEGATED-REFUSAL | Append a refusal reversed by the adverb never, with no citation. | AUDIT: refusal with no citation: `SNu` is never refused. |
| MODAL-PERMISSION | Append a nesting statement written with the modal negation cannot. | AUDIT: naming or refusal statements differ from the ruling: ['Nested `Op (Script A)` cannot be nested.']. |
| CITATION-START | Change the text of lib/rules.ml:1083, the start line of the cited refusal range. | AUDIT: refusal site moved: lib/rules.ml:1083. |
| POSITIVITY-START | Change the text of lib/positivity.ml:85, the start line of the cited refusal range. | AUDIT: refusal site moved: lib/positivity.ml:85. |
| MANIFEST-ROW | Remove the last row of dev/DENOMINATORS.sha256 and run stage-a.sh. | DENOMINATORS FAIL the manifest holds 7 rows and the ruling fixes 8. |
| MANIFEST-SWAP | Replace the corpus/lua/m0-spine.lua row of dev/DENOMINATORS.sha256 with a copy of the dev/bench.sh row, which keeps eight rows, and run stage-a.sh. | DENOMINATORS FAIL the manifest names corpus/twin/interp.c corpus/twin/parser.c corpus/twin/sort.c corpus/twin/spine.c dev/bench.sh dev/bench.sh dev/denominators.json dev/tcc-denominator.sh and the ruling fixes corpus/lua/m0-spine.lua corpus/twin/interp.c corpus/twin/parser.c corpus/twin/sort.c corpus/twin/spine.c dev/bench.sh dev/denominators.json dev/tcc-denominator.sh. |
| NO-SHASUM | Put a shasum that exits 127 first on PATH and run stage-a.sh. | DENOMINATORS FAIL the checksum check failed or shasum is broken. |
| NO-DUNE | Put a dune that exits 127 first on PATH and run stage-a.sh. | R0-COUNT FAIL the scoped dune build failed. |
| NO-DUNE-PATH | Run r0-count.sh with a PATH that holds no dune. | R0-COUNT FAIL dune is not on PATH. |

```text
PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1
```

The Stage A pin mutation required by the M0 plan is PIN-BYTE. The
SIXTH-SHAPE case additionally establishes the count gate's non-vacuity
before Stage B. NO-RG and NO-AWK establish that a gate which reads a tool
fails when that tool fails, because both inherited scripts print their OK
line over an empty read. The nested Script positivity mutation remains
Stage B.

Review round 2 of the review, first fix round, added six cases.
ANCHOR-MOVED covers the anchor leg of the audit, which reads the pin
sources. BLANK-WRAP-NAMING, LIST-WRAP-NAMING and REPHRASED-ADMISSION
cover the whole prose surface of SPEC.md, because a keyword list reads
three phrases only. HEAD-SHA covers the submodule
HEAD comparison, and DENOMINATOR-BYTE covers the eight frozen checksum
entries. REFUSAL-CITATION now reads a citation reason, because the audit
checks the citations of the sentences it read before it compares the set
of sentences with the ruling.

Review round 2 of the review, second fix round, added NESTED-MISSING and
NESTED-HEAD. Git reports a nested gitlink as a changed path, so the whole
tree diff caught both faults first and printed its own reason. The carry
gate now runs the two nested legs before that diff and drops the nested
names from it, and each nested fault prints the reason above.

Review round 2 of the review, third fix round, added NONCOPULA-REFUSAL
and UNTOKENED-NAMING. The claim scan required a copula and a ruled shape
or former token, so a refusal written with the state verb stays and a
naming of an unruled name both passed. The scan now reads a copula or one
of the state verbs stay,
remain, become and continue with a naming, refusal, admission or
permission word, and it reads the sentence whatever its subject is.

Review round 2 of the review, fourth fix round, added NESTED-EXTRA. The
unlisted leg drops every worktree path under a nested gitlink, so a file
in an uninitialized nested checkout passed the carry gate. The gate now
requires an uninitialized nested checkout to be empty, and the case reads
the reason above.

Review round 3 of the review added eleven cases. MANIFEST-ROW, MANIFEST-SWAP
and NO-SHASUM cover the checksum leg, which read the count of the rows the
manifest held, accepted a repeated name in place of a ruled name and ended
the ladder at exit 127 when shasum broke. NO-DUNE and NO-DUNE-PATH cover the
scoped build, which ended the ladder with the shell message alone.
NEGATED-REFUSAL and MODAL-PERMISSION cover negation, because a sentence
that reverses a ruled refusal was no claim sentence at all.
CITATION-START and POSITIVITY-START cover the start line of a cited
range, because only its end line was anchored. NESTED-UNLISTED and
NESTED-TRACKED cover an initialized nested checkout, whose files no leg
read before.

## Stage B 2026-09-10

`python3 -P dev/stage-b-mutations.py` runs the following source mutations
in a temporary repository copy, with positive and restored controls.
The final result was `PASS STAGE-B-MUTATIONS killed=5 restored=1`.

| Mutant | Change | Failing leg |
| --- | --- | --- |
| SIXTH-SHAPE | Append `SSixth` to the pinned shape declaration inventory, rebuild the driver and derive its counts. | R0-COUNT: `built counts differ`; the kernel reports six declared shapes against the inherited five. |
| HOUSE-EXCEPTION | Append one exception site to `surface/schema.ml`. | `dev/house.sh` runs `panicscan --deny present --min present --strict`, which prints `1 finding(s) at or above --deny=present, gate failed (exit 1)`. |
| NESTED-OP | Replace an inline positive Script declaration with `Op (Script A)` in a Script constructor field. | The inherited checker returns `not strictly positive`. |
| LUA-BOUND | Add a 321-line `print/lua.ml` before the implementation stage. | TRUSTED-LINES reports `lua=321/320` and exits nonzero. |
| MISSING-ENCODER | Remove `vendor/kanon/wasm/gc_encode.ml`. | TRUSTED-LINES reports a missing source and exits nonzero. |

One further control is not a mutant. It strips the final newline from
`vendor/kanon/lib/order.ml` and requires `dev/trusted-lines.py` and the
carried `dev/inherited/trusted-lines.sh` to print one kernel number. It
prints `AGREED NEWLINE-COUNT by both trusted-line counters`. Before the
counters were aligned, the same tree printed `kernel=3997/4000` from the
Python leg and `kernel=3996/4000` from the carried leg in one ladder run.

The checker fixture suite separately includes invalid indexes and tags,
integer overflow and noncanonical spelling, WRONGTYPE, slot mismatch,
zero fuel, direct refinement construction, binder capture, duplicate
names, nested and negative recursion, missing imports, import cycles,
sibling-scope leakage, late and malformed headers, a local binder named
`schema`, one named `import` and one named `import` that is applied to a
capitalised name, an imported export
used as a local binder, source-root escape through a symlink and the
1 MiB source limit, each of the last three with a positive control.
Fifty-nine positive and negative checks passed, and the suite now fails
when its case count differs from the recorded number.
The existing Stage A battery still killed all 37 of its mutants with
zero survivors and a restored control.

## Stage C 2026-09-10

The artifact tests run in `dev/stage-c-tests.py`; source inventory tests
run in `dev/stage-c-integrity.py`. All mutations use disposable copies,
with a positive control before mutation and after restoration.

| Mutant | Change | Failing leg |
| --- | --- | --- |
| DROP-LOCAL | Remove `local` from the emitted `bytes` function declaration. Lua syntax still passes. | The strict environment reports `NO-GLOBALS write bytes`. |
| STUB-GLOBAL | Rename the emitted `text` function to `type` and remove its `local`, so the body writes a name the sandbox binds. | The strict environment reports `NO-GLOBALS write type`. |
| BODY-BYTE | Append one newline to the Lua file while preserving the Wasm carrier. | The extracted bytes stay unchanged, which proves the extraction reads the carrier, and LUA-SAME then rejects the body bytes and the carried SHA-1. |
| MISSING-LUA | Remove `print/lua.ml`. | TRUSTED-LINES refuses the missing implemented source. |
| MISSING-TRANSPORT | Remove `print/transport.ml`. | TRUSTED-LINES refuses the missing counted adapter. |
| MISSING-REDIS | Remove `runtime/redis.kan`. | PRELUDE-INTEGRITY refuses the missing prelude. |
| PRELUDE-GROWTH | Append a newline to `runtime/redis.kan`. | PRELUDE-INTEGRITY reports the changed source hash. |
| UNCOUNTED-PRINTER | Add `print/uncounted.ml`. | TRUSTED-LINES refuses an implementation outside its inventory. |

Results: `PASS STAGE-C-MUTATIONS killed=3 restored=1` and
`PASS STAGE-C-INTEGRITY killed=5 restored=1`. The inherited batteries
also pass: Stage B killed=5 and restored=1; Stage A killed=37,
survived=0 and restored=1.

Stage C updates the Stage B LUA-BOUND mutation for the implemented
printer: it appends 321 lines to the existing source, requires the counted
Lua field itself to report the overflowed count against the bound, then
restores the exact original bytes. The expectation is computed from the
count before the mutation, so a failure in another group cannot satisfy
it. The Stage B table above records the earlier pre-implementation
mutation.

### Stage D 2026-09-10: Bash dispatch and body transport

`dev/stage-d-tests.py` runs five mutations in disposable artifacts or
source copies. Each has a passing control before mutation and after
restoration. The default-arm probes exercise the emitted functions with
an unknown reply kind; their stdout must stay empty and their exit must
be 4. The payload dispatch's default arm is unreachable behind the
emitted `envelope`, which already restricts the kind to
number, string, array, null or error, so the DROP-CASE-1 probe replaces
`envelope` with one that sets an unknown kind. The DROP-CASE-0 arm is
reachable on a real envelope. The mutated versions print `accepted`, exposing the missing arm
even though Bash syntax remains valid.

| Mutant | Change | Failing leg |
| --- | --- | --- |
| DROP-CASE-0 | Delete the envelope dispatch's default arm. | Reply comparison accepts an invalid boolean envelope. |
| DROP-CASE-1 | Delete the payload dispatch's default arm. | Reply comparison accepts an unknown variant that the control supplies by replacing `envelope`. |
| SH-BODY-BYTE | Change one byte inside the Bash heredoc. | LUA-SAME differs from the unchanged Lua file and Wasm extraction. |
| MISSING-SH | Delete `print/sh.ml` in the copied source tree. | TRUSTED-LINES refuses a missing implemented printer. |
| SH-BOUND | Append 241 newlines to the copied Bash printer. | TRUSTED-LINES exceeds the existing 240-line bound. |

LUA-SAME also requires the manifest length to equal the body assignments
in `prog.sh`, so a manifest swap cannot empty the byte comparison. The
failure-only artifact carries no body and no assignment. The runner prints its killed census from the
counter that records each kill, not from a literal.

SH-REFUSALS now covers the printer's own budget guard. The front end and
erasure of `M0Spine.tet` spend 2718 polls and the static walk spends 12,
so the case at fuel 2724 refuses with the printer's `SYNTAX SH-BUDGET`,
while the case at fuel 0 refuses with the checker's `CHECK budget`. A
control that deletes the `Kanon_kernel.Budget.exhausted` guard from
`print/sh.ml` fails that case, and the unchanged copy passes it.

Result: `PASS STAGE-D-MUTATIONS killed=5 restored=1`. The complete Stage D
ladder also reran Stage B's five mutations, Stage C's three artifact
mutations and Stage C's five integrity mutations, all with restored
controls. The separate Stage A mutation battery was not rerun in this
slice; the Stage A foundation ladder passed.

### Stage E 2026-09-11: live hosts, decoder ownership and source bounds

`dev/stage-e-tests.py` scores fifteen mutations in temporary artifacts and
copied source trees. The positive control runs before and after each
mutation. The live semantic control uses an owned loopback Redis server
and REST twin and compares stdout bytes against the exact expected value.

| Mutation | Catching check |
| --- | --- |
| INCR becomes DECR in the Bash Lua body, with the expected SHA-1 updated | E2E-3WAY: the LuaJIT, Node and interpreter legs return `9007199254740993` while the mutated Bash leg returns `9007199254740991`, so the four-leg equality fails |
| REST decoder re-exports the Node decoder | DECODERS-SPLIT rejects the merged implementation |
| REST decoder holds a copy of the Node decode body, with no import and its own fault class | DECODERS-SPLIT rejects the copied implementation on token-window overlap |
| Delete store/store.ml | TRUSTED-LINES rejects the missing required source |
| Delete store/interp.ml | TRUSTED-LINES rejects the missing required source |
| Delete runtime/redis-host.mjs | TRUSTED-LINES rejects the missing required source |
| Delete runtime/rest-twin.mjs | TRUSTED-LINES rejects the missing required source |
| Delete runtime/rest-decode.mjs | TRUSTED-LINES rejects the missing required source |
| Exceed the store bound | TRUSTED-LINES fails at the unchanged 200-line limit |
| Exceed the Node host bound | TRUSTED-LINES fails at the unchanged 300-line limit |
| Exceed the REST host bound | TRUSTED-LINES fails at the unchanged 300-line limit |
| Add an uncounted store OCaml source | TRUSTED-LINES rejects the inventory addition |
| Add an uncounted store OCaml interface | TRUSTED-LINES rejects the inventory addition |
| Add an uncounted runtime ECMAScript module | TRUSTED-LINES rejects the inventory addition |
| Add an uncounted runtime `.js` source | TRUSTED-LINES rejects the inventory addition |

Observed in the complete Stage E ladder:
`PASS STAGE-E-INTEGRITY killed=14 restored=1` and
`PASS STAGE-E-MUTATIONS killed=15 restored=1`.
The run also repeated Stage B's five mutations, Stage C's three artifact
and five integrity mutations, and Stage D's five mutations. The separate
Stage A mutation battery was not rerun in this slice; its foundation
ladder passed. Evidence:
`/Users/oobi/Documents/gpt18/tether-stage-e/.kanon-exec/run-PUCGwL`.

### Stage F 2026-09-11: executable body parity and compile work

`dev/stage-f-tests.py` verifies actual Wasm request bodies and Bash
assignment bytes before applying the two required mutations. It restores
the Bash artifact and reruns its positive control. Compile-work mutation
sources and outputs are confined to a temporary directory.

| Mutation | Catching check | Observed result |
| --- | --- | --- |
| Change `bytes(s)` to `bytes(t)` in one Bash-carried Lua body | `dev/lua-same.mjs`, comparing the actual shell value, Lua bytes and Wasm requests | `KILLED ARTIFACT-BYTE by LUA-SAME`; restoration passes |
| Flip one octal digit of an invocation key literal outside the carried body block | `dev/lua-same.mjs`, comparing the shell value, Lua bytes and Wasm requests | `KILLED ARTIFACT-KEY by LUA-SAME`; restoration passes |
| Add checked Nat definitions to a copy of the counter spine, doubling from 2,000 until the real timer crosses the ruled 150 ms bound | The real five-sample parse-through-both-artifacts timer | Crossed at 4,000 definitions on the review machine: `MUTANT-BENCH m0-time median_ms=233.358 min_ms=212.929 max_ms=246.141 runs=5`, `MUTANT-M0-TIME exceeded median_ms=233.358 bound_ms=150` and `KILLED SPINE-WORK by M0-TIME definitions_added=4000` |

The compile-work mutant is calibrated, not fixed at one count. The bound
stays at 150 ms. A machine on which 2,000 definitions compile under the
bound doubles the added work to 4,000, then to 8,000 and to 16,000, and the
runner fails when no count up to 16,000 crosses.

Result: `PASS STAGE-F-MUTATIONS killed=3 survived=0 restored=2`.
A separate boundary control accepts 149 ms and rejects exactly 150 ms,
printing `PASS M0-TIME-BOUNDARY below=149 at=150`. Its synthetic samples
are kept out of production BENCH/PASS output. The compile-work mutant's own
samples are captured the same way and re-emitted with the `MUTANT-BENCH` and
`MUTANT-M0-TIME` prefixes, so a green ladder log holds exactly one `BENCH`
row and one `PASS M0-TIME` row, both from the unmodified spine. The
unmodified spine's independent final measurement passed at 78.261 ms median
on the review machine.

The suite also exercises first-host-fault termination at every invocation,
explicit faults after effects, exact earlier-reply selection, ordinary
versus direct byte lowering, five named emission refusals and the driver's
disagreement exit 3 in two cases, an altered host that exits 0 and an
altered host that exits 9, because a host that disagrees by crashing is
still a disagreement. The trusted-line census counts `bin` under its own
ruled bound of 450 lines, so the Stage C, D and E integrity trees copy
`bin` as well and an uncounted file there prints `TRUSTED-LINES FAIL
uncounted implementation files`. The inherited A through E regression ladder passed,
including B through E mutation batteries; Stage A's separate mutation
battery was not rerun in this slice.

Evidence: `/Users/oobi/Documents/gpt18/tether-stage-f/.kanon-exec/run-fsFrYo`
(functional and mutation suite), `run-2ipnEn` (unmodified benchmark), and
`run-K8oq9l` (inherited ladder), each with exit 0.

### M1 do-notation 2026-09-11: continuation expansion

`python3 -P dev/do-mutations.py` copies the source into a disposable tree,
builds the real expander, and checks the unmodified control before mutation.
Each mutant must compile successfully and then fail the syntax suite with
the marker this table records for it. The runner carries one marker per
row, so a mutant outside the bind arm is killed by its own message.

| Mutation | Change | Caught by | Printed marker |
| --- | --- | --- | --- |
| REPLY-TYPE | Generate a Nat binder where the command supplies Reply. | DO-SYNTAX | `FAIL DO-SYNTAX continuation differs:` |
| ACTION-ORDER | Apply the continuation to the action instead of the action to the continuation. | DO-SYNTAX | `FAIL DO-SYNTAX continuation differs:` |
| LOST-TAIL | Replace the continuation body with nil. | DO-SYNTAX | `FAIL DO-SYNTAX continuation differs:` |
| FINAL-SEMI | Accept a second semicolon before the final expression instead of refusing it. | DO-SYNTAX | `FAIL DO-SYNTAX malformed do accepted:` |

All four were killed. The runner restores the original source, rebuilds,
and requires the complete syntax suite to pass. The live checkout is never
mutated. Result: `PASS DO-MUTATIONS killed=4 survived=0 restored=1`.
Evidence: `tether-m1-do/.kanon-exec/run-WozCfU`, exit 0, for the first
three rows; the FINAL-SEMI row was added in the review round of
2026-09-11 and is recorded in `dev/M1-BUILD-LOG.md`.

### M1 read-only dispatch 2026-09-11

`python3 -P dev/readonly-mutations.py` checks the unmodified host and shell
suites, then changes one production source at a time in a disposable
copy. Each mutant must compile and fail the named assertion below. Node
uses an explicit TAP reporter so the failed-test marker is deterministic.

| Mutation | Change | Required failed assertion |
| --- | --- | --- |
| NODE-MODE | Select ordinary evaluation for a canonical no-writes body. | `RO-NODE load once` |
| NODE-FALLBACK | Use EVAL instead of EVAL_RO after NOSCRIPT. | `RO-NODE load once` |
| SH-MODE | Emit the ordinary suffix for a read-only Bash invocation. | `RO-SH fallback order` |
| REST-ALLOWLIST | Refuse both read-only commands at the local REST endpoint. | `RO-REST admits` |

All four were killed. The original sources were restored and rebuilt,
and the two suites the runner drives passed again. Those two are the
complete host suite and the shell-only transcript suite
(`dev/readonly-tests.py --shell-only`), which skips the live legs
RO-LIVE and RO-E2E, so the runner never reruns them. Result:
`PASS RO-MUTATIONS killed=4 survived=0 restored=2`.
Evidence: `/Users/oobi/Documents/gpt18/tether-m1-readonly/.kanon-exec/run-cLciPj`,
exit 0. The live checkout was not mutated.

The review round of 2026-09-11 added the host case
`RO-NODE header classification follows the compiler source` and made the
RO-SH, RO-LIVE and RO-E2E rows report counted quantities. The four
mutants and their required assertions did not change.

### M1 String and key commands 2026-09-12

`python3 -P dev/strings-mutations.py` changes one production source at a
time in a disposable copy. Every mutant builds successfully and must fail
its specific assertion. The unit and offline integration suites pass
before mutation and again after restoring and rebuilding the sources.

| Mutation | Change | Required failed assertion |
| --- | --- | --- |
| EXISTS-WRITE | Remove EXISTS from the read-only allowlist. | `STRINGS write classification` |
| DECIMAL-ROUND | Convert the post-arithmetic GET through a Lua number. | `STRINGS LuaJIT reply` |
| NEGATIVE-OVERFLOW | Disable the negative overflow check in the store. | `FAIL STRINGS-UNIT overflow` |
| DEL-KEEPS-KEY | Return the deletion count without removing the stored key. | `FAIL STRINGS-UNIT delete` |

Result: `PASS STRINGS-MUTATIONS killed=4 survived=0 restored=2`.

The review round of 2026-09-12 split the generic key assertion of
`dev/strings_tests.ml` into `STRINGS-UNIT wrong type`, `STRINGS-UNIT set
replaces` and `STRINGS-UNIT delete`, so DEL-KEEPS-KEY now requires the
delete assertion alone. A store mutant that only changes the SET status
byte fails `STRINGS-UNIT set replaces` and no longer prints the
DEL-KEEPS-KEY reason. The runner counts survivors instead of raising on
the first one, and it counts the two restored control runs, so `survived`
and `restored` report observed quantities.
Evidence: `/Users/oobi/Documents/gpt18/tether-m1-strings/.kanon-exec/run-mCLFw9`,
exit 0. The working checkout was unchanged by this run.
