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

### M1 Hash commands 2026-09-12

`python3 -P dev/hashes-mutations.py` compiles one production-source mutant
at a time in a disposable copy. The unit and offline suites pass before
mutation and after the original sources are restored and rebuilt. Each
mutant must compile successfully and fail its named assertion.

| Mutation | Change | Required failed assertion |
| --- | --- | --- |
| HGET-WRITE | Remove HGET from the read-only allowlist. | `HASHES write classification` |
| HSET-COUNT | Report a new field when replacing an existing field. | `FAIL HASHES-UNIT overwrite count` |
| HDEL-EMPTY-KEY | Retain an existing key after deleting its last field, preserving missing-key behavior. | `FAIL HASHES-UNIT delete last field` |
| HINCRBY-ROUND | Convert the post-increment HGET through a Lua number. | `HASHES LuaJIT reply` |
| INTERP-ERR-TAG | Answer a store fault with the `bulk` constructor instead of `err`. | `FAIL HASHES-UNIT hset wrong type stops client` |
| HASH-FAULT-MESSAGE | Report the String fault text for an invalid stored hash decimal. | `HASHES store reply` |

Result: `PASS HASHES-MUTATIONS killed=6 survived=0 restored=2`.
INTERP-ERR-TAG covers `store/interp.ml`, which had no mutant before this
review round. The unit suite now drives every command fault through
`I.run` and requires the `err` reply that stops the Client, so the
constructor swap fails a named assertion. HASH-FAULT-MESSAGE covers
`store/store.ml` message text: the offline oracle compares the reply
bytes of the invalid-decimal rows, so the String text fails there.
The earlier HDEL-EMPTY-KEY version also created a key on a missing-key
HDEL. It failed the earlier `missing delete` assertion and was therefore
not counted as a kill of the named assertion. The narrowed mutant above
is killed specifically by the last-field deletion check.

Evidence: `/Users/oobi/Documents/gpt18/tether-m1-hashes/.kanon-exec/run-3GbMit`,
exit 0. The working checkout was unchanged by the mutation runner.

### M1 Set commands 2026-09-12

`python3 -P dev/sets-mutations.py` compiles production-source mutants in
a disposable copy. The unit and offline controls run before mutation
and after source restoration and rebuilding. Each mutant must compile
and fail the specific assertion below to count as killed.

| Mutation | Change | Required failed assertion |
| --- | --- | --- |
| SADD-COUNT | Report one when adding an existing member. | `FAIL SETS-UNIT duplicate count` |
| SREM-EMPTY-KEY | Retain an existing key after removing its last member, preserving missing-key behavior. | `FAIL SETS-UNIT remove last member` |
| SISMEMBER-WRITE | Remove SISMEMBER from the read-only allowlist. | `SETS write classification` |
| SCARD-WRITE | Remove SCARD from the read-only allowlist. | `SETS write classification` |
| SADD-READONLY | Classify SADD as read-only. | `SETS write classification` |
| SET-LUA-COUNT | Emit zero for every integer count reply. | `SETS LuaJIT reply` |
| SET-ERR-TAG | Encode a store fault as `bulk` instead of `err`. | `FAIL SETS-UNIT sadd wrong type stops client` |
| SET-LUA-ERR-TAG | Encode an emitted count-path fault as `bulk` instead of `err`. | `TWIN reply kind string wanted status` |

Result: `PASS SETS-MUTATIONS killed=8 survived=0 restored=2` in the
review round ladder `gates-fix-2.log`. Every named mutant compiled and
failed its specified assertion. Both restored controls, the unit suite
and the offline suite, passed; the runner left the working sources
unchanged. The STATIC suite is a kill test, not a control.
This Set mutation result passed within a full ladder whose aggregate
exit was 1 solely from the separate M0 timing leg and its cascades.

### M1 List commands 2026-09-12

`dev/lists-mutations.py` rebuilds each mutant in a disposable copy and
requires its specific failed assertion. Passing unit and offline controls
run before mutation and after restoring and rebuilding the source.

| Mutation | Change | Required failed assertion |
| --- | --- | --- |
| RIGHT-ORIENTATION | Use left-end order for right-end operations. | `FAIL LISTS-UNIT right push order` |
| RPOP-REMAINDER | Keep the reversed remainder after a right pop. | `FAIL LISTS-UNIT right pop order` |
| POP-EMPTY-KEY | Retain a key after removing its last element. | `FAIL LISTS-UNIT left deletes last key` |
| LLEN-COUNT | Return zero for nonempty lists. | `FAIL LISTS-UNIT length includes duplicates` |
| LLEN-WRITE | Remove LLEN from the read-only allowlist. | `LISTS write classification` |
| LPOP-READONLY | Admit LPOP to the read-only allowlist. | `LISTS write classification` |
| LIST-LUA-DIRECTION | Swap LPUSH and RPUSH in emitted Lua. | `TWIN list order mismatch` |
| LIST-LUA-NIL | Encode a missing pop as empty bulk. | `TWIN reply kind string wanted nil` |
| LIST-ERR-TAG | Encode a store fault as bulk. | `FAIL LISTS-UNIT lpush wrong type stops client` |

The Hash and Set empty-key mutants now target their calls to the shared
`save` helper. The Hash mutant preserves missing-key deletion so its
failure still identifies an existing hash whose final field was removed.
The Set mutant continues to preserve missing-key behavior through SREM's
existing absent-member branch. Their kill assertions are unchanged.

The full ladder in
`/Users/oobi/Documents/gpt18/tether-m1-lists/.kanon-exec/run-quMkCs`
recorded `PASS LISTS-MUTATIONS killed=9 survived=0 restored=2` and
`PASS SETS-MUTATIONS killed=8 survived=0 restored=2`. Each List mutant
compiled and failed its named assertion, and both restored controls
passed. The Hash mutant's first replacement failed the earlier
`missing delete` assertion and therefore did not count as killed. Its
corrected replacement preserves that case without changing the required
`delete last field` assertion.

The corrected Hash suite completed in
`/Users/oobi/Documents/gpt18/tether-m1-lists/.kanon-exec/run-ksAlmF`
with exit 0, no stderr and `PASS HASHES-MUTATIONS killed=6 survived=0
restored=2`. HDEL-EMPTY-KEY failed `FAIL HASHES-UNIT delete last field`.
The unit and offline restored controls passed. The earlier full ladder
retains its exit 1 from the first Hash fixture and its aggregate
failures; all functional legs and the separate M0 timing leg passed.

The List runner also runs `python3 -P dev/lists-tests.py --static` as a
control before mutation and requires `PASS LISTS-REFUSALS`. The
documented static command therefore cannot stop checking refusals and
the interpreter examples without a red ladder. That control runs before
mutation, so the runner still reports `restored=2` from the unit and
offline controls after it restores the source.

### M1 List access commands 2026-09-13

`python3 -P dev/list-access-mutations.py` builds each mutant in a
disposable copy and requires both exit 1 and the intended diagnostic.
The 83-case unit suite and five selected artifact/LuaJIT probes run as
controls before mutation and after restoration. A missing or duplicate
anchor, failed build, survivor, or failed control makes the run fail.

| Mutant | Change | Required failure |
| --- | --- | --- |
| INDEX-NEGATIVE | Drop the list length when normalizing a negative index | `FAIL LIST-ACCESS-UNIT index negative` |
| INDEX-MISSING | Return empty bulk for a missing index | `FAIL LIST-ACCESS-UNIT missing index before invalid integer` |
| LSET-POSITION | Replace every position except the selected one | `FAIL LIST-ACCESS-UNIT set first` |
| LTRIM-END | Exclude the stop element | `FAIL LIST-ACCESS-UNIT trim inclusive` |
| LTRIM-EMPTY-KEY | Retain an empty List key | `FAIL LIST-ACCESS-UNIT trim reversed deletes key` |
| LIST-ACCESS-ERR-TAG | Retag store errors as bulk replies | `FAIL LIST-ACCESS-UNIT set missing stops client` |
| LINDEX-WRITE | Remove LINDEX from the read-only allowlist | `LIST-ACCESS write classification` |
| LTRIM-READONLY | Admit LTRIM as read-only, including an untaken branch | `LIST-ACCESS write classification` |
| LUA-INDEX | Always emit index zero | `LISTS LuaJIT reply` |
| LUA-REPLACEMENT | Use the index bytes as the replacement | `TWIN list order mismatch` |
| LUA-STATUS-TAG | Retag Redis status replies as bulk | `TWIN reply kind string wanted status` |
| LUA-ERR-TAG | Retag Redis error replies of the shared reply block as status | `TWIN reply kind status wanted string` |

Focused capture `run-6VG6Na` under
`/Users/oobi/Documents/gpt18/tether-m1-list-access/.kanon-exec/` ended
`PASS LIST-ACCESS-MUTATIONS killed=11 survived=0 restored=6`, exit 0,
before the review round. The review round of 2026-09-13 adds the
LUA-ERR-TAG row of the table above, so the runner prints
`PASS LIST-ACCESS-MUTATIONS killed=12 survived=0 restored=6`, the row of
the review ladder. The complete ladder result is recorded in
`dev/M1-BUILD-LOG.md`.

### M1 List range controls, 2026-09-13

`dev/list-range-mutations.py` compiles each mutation in a disposable copy
and requires the intended assertion to fail. It runs five positive
controls before and after mutation: the unit suite and the all, branch,
tail and head probes. Each control requires its own complete row, so a
control that stops checking what it names cannot pass. Build failures do
not count as killed mutants.

| Mutation | Change | Required failure |
| --- | --- | --- |
| RANGE-END | Exclude the stop element | `FAIL LIST-RANGE-UNIT range all` |
| ARRAY-ORDER | Reverse interpreter array elements | `FAIL LIST-RANGE-UNIT range all` |
| ARRAY-BULK | Encode interpreter elements as status | `FAIL LIST-RANGE-UNIT range all` |
| RANGE-STATE | Drop the store after a read | `FAIL LIST-RANGE-UNIT range all` |
| LRANGE-WRITE | Remove LRANGE from the read-only allowlist | `LIST-RANGE write classification` |
| BRANCH-READONLY | Admit LTRIM in an untaken write arm | `LIST-RANGE write classification` |
| LUA-ARRAY-ORDER | Reverse Lua array elements | `LISTS LuaJIT reply` |
| LUA-RANGE-STOP | Use the start index for the stop | `LISTS LuaJIT reply` |
| LUA-ARRAY-TAG | Retag the array as nil | `TWIN reply kind nil wanted array` |
| LUA-ARRAY-ELEMENT | Retag a selected bulk element as status | `TWIN reply kind status wanted string` |
| LUA-ERR-TAG | Retag the error reply of the List arm as a bulk string | `TWIN reply kind string wanted status` |

The existing SADD-COUNT anchor now selects the SADD wrapper only;
its required failure remains `FAIL SETS-UNIT duplicate count`.
Execution results are recorded in the List range entry of `dev/M1-BUILD-LOG.md`.

Capture `run-TZI6fw` in the List range checkout printed
`PASS LIST-RANGE-MUTATIONS killed=10 survived=0 restored=5`, before the
review round. The review round of 2026-09-13 adds the LUA-ERR-TAG row of
the table above, so the runner prints
`PASS LIST-RANGE-MUTATIONS killed=11 survived=0 restored=5`, the row of
the review ladder.
The narrowed Set control was rerun in `run-N7X7nM`, which printed
`KILLED SADD-COUNT by FAIL SETS-UNIT duplicate count` and
`PASS SETS-MUTATIONS killed=8 survived=0 restored=2`, exit 0.

### M1 Set enumeration mutations, 2026-09-14

`dev/set-members-mutations.py` builds every mutant in a temporary source
copy and requires its intended assertion to fail. The unit suite and
the all, branch and head LuaJIT probes pass before and after mutation.

| Mutant | Change | Required assertion |
| --- | --- | --- |
| MEMBERS-ORDER | Reverse store member order | `FAIL SET-MEMBERS-UNIT unique order` |
| MEMBERS-STATE | Discard the store after enumeration | `FAIL SET-MEMBERS-UNIT missing` |
| MEMBERS-WRITE | Remove the SMEMBERS read-only exemption | `SET-MEMBERS write classification` |
| MEMBERS-BRANCH | Treat a reachable SREM as read-only | `SET-MEMBERS write classification` |
| LUA-MEMBERS-SORT | Reverse the array sort | `SET-MEMBERS LuaJIT member order` |
| LUA-BYTE-ORDER | Reverse the byte comparison | `SET-MEMBERS LuaJIT member order` |
| LUA-PREFIX-ORDER | Put longer equal prefixes first | `SET-MEMBERS LuaJIT member order` |
| LUA-MEMBERS-ARRAY | Replace the array tag with nil | `TWIN reply kind nil wanted array` |
| LUA-MEMBERS-BULK | Replace bulk element tags with status | `TWIN reply kind status wanted string` |

Review round 2026-09-14 narrowed the three ordering mutants. The suite
wraps each LuaJIT comparison in `dev/set-members-tests.py`, so a sorted
array case reports `SET-MEMBERS LuaJIT member order` and every other
case keeps its own reason. The shared helper is unchanged, so the lists,
sets, hashes, list access and list range ladders keep their markers.

The complete ladder's capture `run-cUQ1BJ` records
`PASS SET-MEMBERS-MUTATIONS killed=9 survived=0 restored=4`. The shared LRANGE branch retains all eleven
List range mutant kills and their five restored controls.

## 2026-09-14: Hash enumeration

`dev/hash-entries-mutations.py` builds every mutant in a disposable copy
and requires both exit 1 and the intended assertion marker. Four controls
run before mutation and after restoring and rebuilding the source.

| Mutant | Required assertion |
| --- | --- |
| ENTRIES-ORDER | HASH-ENTRIES-UNIT pair order |
| ENTRIES-PAIR | HASH-ENTRIES-UNIT pair order |
| ENTRIES-STATE | HASH-ENTRIES-UNIT missing |
| ENTRIES-WRITE | HASH-ENTRIES write classification |
| ENTRIES-BRANCH | HASH-ENTRIES write classification |
| LUA-FIELD-SORT | HASH-ENTRIES LuaJIT field/value order |
| LUA-PAIR-STRIDE | HASH-ENTRIES LuaJIT field/value order |
| LUA-FIELD-BYTES | HASH-ENTRIES LuaJIT field/value order |
| LUA-FIELD-PREFIX | HASH-ENTRIES LuaJIT field/value order |
| LUA-ENTRIES-ARRAY | TWIN reply kind nil wanted array |
| LUA-ENTRIES-BULK | TWIN reply kind status wanted string |

Review round 2026-09-14 added the `decimal order` store case, so the unit
control of this suite now requires `PASS HASH-ENTRIES-UNIT cases=16`. The
mutant inventory, the required assertions and the four controls are unchanged.

The complete ladder recorded `PASS HASH-ENTRIES-MUTATIONS killed=11
survived=0 restored=4` and `PASS HASH-ENTRIES-COUNTS`. The separate foundation
battery recorded `PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1`.
The ladder's only root failure was the independent M0 timing limit; the
unchanged timing command passed separately at 115.406 ms. See the Hash
enumeration entry in `dev/M1-BUILD-LOG.md` for the full validation scope.

The existing Hash overwrite-count, List array traversal/error and Set
state/order mutation anchors follow the shared implementation. Their
required assertions and inventories remain unchanged. The revised Hash
count mutant preserves HDEL behavior and reaches the original HSET
overwrite-count assertion.

### 2026-09-14: M1 Hash projections

`dev/hash-projections-mutations.py` builds each mutant in a disposable
copy. A kill requires compilation to pass and the selected test to fail
with its intended assertion. Unit, keys, values, both write-branch probes
and the value-head probe run as controls before and after mutation.

| Mutant | Required detection |
| --- | --- |
| PROJECTION-TAGS | Unit projection contents |
| PROJECTION-ORDER | Unit value order |
| KEYS-ORDER | Unit field order |
| PROJECTION-DUPLICATES | Unit duplicate preservation |
| PROJECTION-STATE | Unit missing-key state preservation |
| KEYS-WRITE | HKEYS read-only classification |
| VALS-WRITE | HVALS read-only classification |
| KEYS-BRANCH | Reachable write after HKEYS |
| VALS-BRANCH | Reachable write after HVALS |
| LUA-KEYS | HKEYS LuaJIT projection contents |
| LUA-VALS | HVALS LuaJIT projection contents |
| LUA-PROJECTION-SORT | HVALS LuaJIT order |
| LUA-PROJECTION-BYTES | HKEYS LuaJIT unsigned byte order |
| LUA-PROJECTION-PREFIX | HKEYS LuaJIT prefix order |
| LUA-PROJECTION-ARRAY | Missing-key array reply kind |
| LUA-PROJECTION-BULK | Value-head bulk reply kind |

Validation in `tether-m1-hash-projections/.kanon-exec/run-ASfVMg` completed
with `PASS HASH-PROJECTIONS-MUTATIONS killed=16 survived=0 restored=6`.
The surrounding scoped array-command validation also completed with exit 0.

The existing LRANGE typed-error mutation anchor tracks the expanded array
branch (tags 27 through 31); its assertion and required failure are
unchanged. The previous Set and Hash enumeration mutation anchors remain
intact.

### 2026-09-14: M1 Set algebra

`dev/set-algebra-mutations.py` compiled and killed 17 mutants in a
disposable copy, then rebuilt and passed all six controls. It checks
each intended assertion and exit status, so a build failure or unrelated
error cannot score a kill. Capture:
`tether-m1-set-algebra/.kanon-exec/run-DQA2xc`.

| Mutant | Required detection |
| --- | --- |
| STORE-UNION | Left-only union members |
| STORE-INTER | Left-only intersection is empty |
| STORE-DIFF | Right-only difference is empty |
| STORE-SECOND-KEY | Right input is read independently |
| STORE-ORDER | Ordered complete reply |
| STORE-STATE | Missing-key read preserves the sentinel |
| STORE-KEY-OPERAND | A key operand retains its distinct shape |
| LUA-SECOND-KEY | Difference receives the declared second key |
| LUA-UNION | Union command selection |
| LUA-INTER | Intersection command selection |
| LUA-DIFF | Difference command selection |
| UNION-WRITE | Union is classified read-only |
| INTER-WRITE | Intersection is classified read-only |
| DIFF-WRITE | Difference is classified read-only |
| BRANCH-WRITE | A reachable delete removes read-only classification |
| LUA-ORDER | Reverse twin output is sorted |
| LUA-BULK | Head projection retains the bulk reply variant |

Result: `PASS SET-ALGEBRA-MUTATIONS killed=17 survived=0 restored=6`.
The earlier LRANGE error-tag anchor now spans array tags 27 through 34;
its expected assertion and required failure are unchanged.

### 2026-09-15: M1 Set store mutations

`python3 -P dev/set-store-mutations.py` works in a disposable copy.
Each mutant must compile, exit with the intended assertion failure,
and restore before the next mutation. The six controls pass before
mutation and after restoration.

| Mutant | Required observation |
| --- | --- |
| STORE-UNION | A source present only on the left contributes to union. |
| STORE-INTER | A missing right input makes the intersection empty. |
| STORE-DIFF | A source present only on the right contributes no difference. |
| STORE-DESTINATION | The destination receives or removes the result. |
| STORE-EMPTY | An empty result deletes the destination key. |
| STORE-COUNT | The reply contains the result cardinality. |
| STORE-ALIAS | Input values are read before replacing an aliased destination. |
| STORE-SECOND-SOURCE | The second source is read independently. |
| LUA-UNION | Emitted union stores the union members. |
| LUA-INTER | Emitted intersection removes an empty destination. |
| LUA-DIFF | Emitted difference retains operand order. |
| LUA-DESTINATION | Emitted writes target the destination. |
| LUA-SECOND-SOURCE | Emitted code reads the second source. |
| LUA-COUNT | Emitted code returns the stored cardinality. |
| LUA-REPLY-TAG | A case expression observes the integer reply constructor. |
| UNION-READONLY | Union store has write classification. |
| INTER-READONLY | Intersection store has write classification. |
| DIFF-READONLY | Difference store has write classification. |

The shared LuaJIT oracle helper takes the reason of the calling slice.
`LUA-COUNT` and `LUA-REPLY-TAG` therefore require the observation
`SET-STORE LuaJIT reply`, not the Set algebra text. The mutations and
the controls are unchanged.

The completed `run-IKgU4u` ladder capture reports
`PASS SET-STORE-MUTATIONS killed=18 survived=0 restored=6`.
The unchanged assertion of the earlier Set algebra difference mutant
uses a narrower branch anchor and still passes in that capture.

The full run found that the earlier `LTRIM-EMPTY-KEY` anchor matched
both the Set and List empty-result expressions. Its anchor now selects
`(List values)` explicitly, keeping the same failure assertion and
12-mutant requirement. The scoped recovery capture `run-hI6Pny`
reports `PASS LIST-ACCESS-MUTATIONS killed=12 survived=0 restored=6`.
The build log records the full ladder's timing failure and this recovery.

### 2026-09-15: M1 Set move mutation checks

`dev/set-move-mutations.py` runs mutants in a disposable copy, compiles
each changed tree and requires the expected semantic failure. It restores
the affected file in a finally block and reruns five positive controls
after all mutants. A wrong exit status, missing diagnostic, build error,
missing anchor, changed inventory or survivor fails the run.

| Mutants | Detector |
| --- | --- |
| STORE-DIRECTION, STORE-MEMBER | Interpreter reply and complete-state checks. |
| STORE-MISSING-SOURCE | Named `missing source precedence` check: a missing source answers before the destination type. |
| STORE-DESTINATION-TYPE | Existing source must check a wrong destination even for an absent member. |
| STORE-NO-OP, STORE-ALIAS | Literal zero/one replies for absent members and same-key transfers. |
| STORE-REMOVAL | Complete source and destination values after a transfer. |
| STORE-EXISTING-MEMBER | A transfer still returns one when the destination already has the member. |
| LUA-COMMAND, LUA-DIRECTION, LUA-MEMBER | Independent LuaJIT complete-state checks, pinned on `TWIN stored value mismatch`. |
| LUA-REPLY-TAG | A typed continuation distinguishes integer from bulk replies. |
| WRITE-FLAG | Writer header assertion before running the artifact. |
| TWIN-MISSING-SOURCE, TWIN-ALIAS | Literal replies in the parity fixtures. |

The positive controls are the 304-case unit suite and the move, same-key,
typed-reply and binary-member artifact probes. The focused capture
`/Users/oobi/Documents/gpt18/tether-m1-set-move/.kanon-exec/run-WFxoQR`
reports `PASS SET-MOVE-MUTATIONS killed=15 survived=0 restored=5`.
The new ladder requires this exact inventory row.

Existing Set algebra and Set store mutations keep their original semantic
changes after the new shared lookup and Lua argument selection. Their
operand anchors are made unique; neither mutant nor positive-control
inventory is reduced. The old unknown-tag test advances from 38 to 39.

The full Set move ladder independently repeats the green mutation row at
stdout line 636 of `run-kSWHFI`, followed by `PASS SET-MOVE-COUNTS` and
`PASS M1-SET-MOVE`. All preceding mutation suites pass in that run,
including the unchanged 17-mutant Set algebra and 18-mutant Set store
inventories. The build log records the full capture and green timing gate.

### 2026-09-15: M1 TTL mutation checks

`python3 -P dev/ttl-mutations.py` copies the source into a disposable
tree, builds every mutant, and requires its intended assertion to fail
with exit 1. A compiler failure, unexpected diagnostic or surviving
mutant fails the runner. The source is restored after each attempt.

| Mutation | Required failure |
| --- | --- |
| CLOCK-BOUNDARY | PTTL returns zero at the deadline before the key expires. |
| EXPIRE-SCALE | EXPIRE seconds must convert to milliseconds. |
| TTL-ROUNDING | Half-second TTL results round up. |
| TTL-MISSING | Expired keys return the missing sentinel. |
| SET-EXPIRY | Replacing a value clears the deadline. |
| PERSIST-EXPIRY | PERSIST removes metadata and changes only once. |
| STORE-REPLY-RANGE | The store rejects an inexact expiry reply. |
| INTERPRETER-UNIT | The erased EXPIRE tag selects seconds. |
| LUA-UNIT | Printed EXPIRE selects seconds in the independent twin. |
| LUA-REPLY-RANGE | An inexact TTL becomes an error reply. |
| READ-FLAG | TTL receives read-only dispatch. |
| WRITE-FLAG | EXPIRE remains writing, including for missing keys. |
| TWIN-SCALE | The twin preserves seconds-to-milliseconds conversion. |

Five controls, the store unit suite plus the seconds, inexact-reply,
missing-TTL and missing-EXPIRE probes, pass before mutation and again
after restoration. The store unit control requires the counted row
`PASS TTL-UNIT cases=146`, so a deleted store check breaks the control.
Final result:

```text
PASS TTL-MUTATIONS killed=13 survived=0 restored=5
```

The inherited DEL, Hash deletion, Set store alias and SMOVE mutation
anchors now use the explicit store value-map accessors. The Set error-tag
anchor follows the added expiry guard. STORE-DESTINATION now redirects
both the destination write and expiry cleanup to the wrong source key,
preserving the original defect and missing-destination assertion. The
full ladder initially caught that mutant at a different assertion; the
corrected full Set store mutation suite passed with 18 kills and six
restored controls in `.kanon-exec/run-i6Bsnz`. Their behavior checks and
expected diagnostics are retained. The current Stage D static-walk
negative control still grants six polls and requires `SH-BUDGET`.

## 2026-09-16 M1 absolute expiry

`python3 -P dev/absolute-expiry-mutations.py` compiled each changed tree
before requiring its intended runtime assertion. The 14 cases cover:

| Cases | Fault inserted | Required witness |
| --- | --- | --- |
| STORE-AT-BASE, STORE-TIME-BASE | Add or subtract the clock for an absolute timestamp | ABSOLUTE-UNIT absolute milliseconds |
| INTERPRETER-AT, INTERPRETER-TIME | Dispatch an absolute command as relative | Nonzero-clock interpreter reply |
| LUA-AT, LUA-PAT | Swap seconds and milliseconds in deadline setters | Twin expiry mismatch |
| LUA-TIME, LUA-PTIME | Swap units in timestamp readers | LuaJIT reply mismatch |
| READ-TIME-FLAG, READ-PTIME-FLAG | Mark a timestamp reader as writing | Write classification |
| WRITE-AT-FLAG, WRITE-PAT-FLAG | Mark a deadline setter as read-only | Write classification |
| TWIN-AT-BASE, TWIN-TIME-BASE | Apply relative arithmetic in the independent twin | Twin expiry or reply mismatch |

Eight controls run before mutation and after restoration. The focused
run in `.kanon-exec/run-bwmd4V` completed with exit 0:

```text
PASS ABSOLUTE-MUTATIONS killed=14 survived=0 restored=8
```

The inherited TTL interpreter-unit anchor now follows the shared
relative/absolute dispatcher and still swaps only the relative units.
The Stage D negative control remains a six-poll static walk at fuel
44262, after measuring 44256 checker/erasure polls and 12 walk polls.

## 2026-09-16 M1 conditional expiry

`python3 -P dev/conditional-expiry-mutations.py` checks 17 source changes
in disposable trees. Every changed tree must build, then fail the
assertion named by its mutation row.

| Cases | Fault inserted | Required witness |
| --- | --- | --- |
| STORE-NX, STORE-XX | Reverse the expiry-presence condition | Store condition matrix reply |
| STORE-GT-EQUAL, STORE-LT-EQUAL | Accept equal deadlines | Store condition matrix reply |
| STORE-GT-INFINITY, STORE-LT-INFINITY | Reverse persistent-key comparison | Store condition matrix reply |
| INTERPRETER-CONDITION | Decode NX as XX | Interpreter reply mismatch |
| INTERPRETER-CLOCK | Treat absolute conditional expiry as relative | Nonzero-clock interpreter reply |
| LUA-NX, LUA-GT | Emit a different condition | Twin expiry mismatch |
| LUA-PAT | Emit seconds for a millisecond timestamp | Twin expiry mismatch |
| TWIN-NX | Ignore NX on a volatile key | Twin expiry mismatch |
| TWIN-PRECISION | Compare adjacent large deadlines through Lua numbers | Twin expiry mismatch |
| WRITE-FLAG-48 through WRITE-FLAG-51 | Mark a conditional setter as read-only | Write classification |

Ten controls run before the mutations and after restoration. The focused
run in `/Users/oobi/Documents/gpt18/tether-m1-conditional-expiry/.kanon-exec/run-9ObNSX`
completed with exit 0:

```text
PASS CONDITIONAL-MUTATIONS killed=17 survived=0 restored=10
```

The added prelude moves the checker/erasure cost to 51636 polls. A separate
measurement recorded 12 static-walk polls. Stage D now grants six walk
polls at fuel 51642 and still requires `SH-BUDGET` without output creation;
its complete refusal and mutation suites passed in `run-YjlZjF` before
the larger historical ladder was stopped for scoped expiry validation.

Review round 2026-09-16 raises the unit control of the suite from
`PASS CONDITIONAL-UNIT cases=875` to `PASS CONDITIONAL-UNIT cases=878`.
The three added store assertions pin the seconds scale of a conditional
install, relative and absolute, and the state after a rejected seconds
install. No mutant row changes: the ten controls and the 17 mutants of the
table above are unchanged.

## 2026-09-17 M1 variadic HMGET

`python3 -P dev/hmget-mutations.py` builds every mutation before running
a named semantic assertion. Compile failures do not count as kills.
Each source file is restored in a `finally` block; six controls are
rebuilt and rerun after the final mutation.

| Mutation | Fault inserted | Required witness |
| --- | --- | --- |
| STORE-ORDER | Reverse the reply list of the store | FAIL HMGET-UNIT store preserves order, nils and duplicates |
| STORE-DROP | Drop every field after the first | FAIL HMGET-UNIT store preserves order, nils and duplicates |
| STORE-DUPLICATES | Collapse duplicate field requests | FAIL HMGET-UNIT store preserves order, nils and duplicates |
| STORE-NIL | Reply with empty bytes for a missing field | FAIL HMGET-UNIT store preserves order, nils and duplicates |
| STORE-TYPE | Read a non-Hash key as an empty Hash | FAIL HMGET-UNIT store wrong type |
| INTERPRETER-ARGS | Decode the key as the first field | FAIL HMGET-UNIT interpreter reply and complete state |
| INTERPRETER-STATE | Return an empty store after the read | FAIL HMGET-UNIT interpreter reply and complete state |
| INTERPRETER-NIL | Encode a nil field as an empty bulk | FAIL HMGET-UNIT interpreter reply and complete state |
| READONLY | Classify tag 52 as a writer | HMGET write classification |
| LUA-ORDER | Walk the reply order forward | LISTS LuaJIT reply |
| LUA-ARGUMENT-ORDER | Flatten the bulkMore spine forward | LISTS LuaJIT reply |
| LUA-NIL | Emit empty bytes for a missing field | LISTS LuaJIT reply |
| LUA-LAST-FIELD | Send a fixed name for the last field | LISTS LuaJIT reply |
| LUA-ARRAY | Tag the reply array as nil | TWIN reply kind nil wanted array |
| TWIN-ARGS | Forward only the first field in the twin | LISTS LuaJIT reply |
| TWIN-NIL | Reply with empty bytes for a missing field in the twin | LISTS LuaJIT reply |

Every name of the table is the name the runner prints in its `KILLED NAME`
row, so a ladder log matches this record row by row.

The controls are the 26-scenario unit executable and the lookup,
single-field, within-script snapshot, cross-script snapshot and computed
field-list probes. The suite requires 16 killed mutations, zero survivors
and six restored controls.

The full ladder capture `run-fIAb5S` under
`/Users/oobi/Documents/gpt18/tether-m1-hmget/.kanon-exec/` records:

```text
PASS HMGET-MUTATIONS killed=16 survived=0 restored=6
PASS LIST-RANGE-MUTATIONS killed=11 survived=0 restored=5
```

The existing LRANGE ARRAY-BULK and LUA-ERR-TAG anchors now match the
generalized array encoder. Their original assertions are unchanged and
both mutations still fail at those assertions. No trusted-source or
timing bound changed.

## M1 List bulk pushes, 2026-09-17

`dev/list-bulk-mutations.py` builds every mutant before requiring a
nonzero exit at its named semantic assertion. It uses an isolated copy,
restores each edited file, rebuilds, and reruns all six controls.

| Mutation | Deliberate defect | Required witness |
| --- | --- | --- |
| STORE-ORDER | Keep the tail in request order before prepending | LIST-BULK-UNIT store order, count and complete state |
| STORE-DROP | Drop all tail values | LIST-BULK-UNIT store order, count and complete state |
| STORE-FIRST | Corrupt the first value | LIST-BULK-UNIT store order, count and complete state |
| STORE-EXPIRY | Remove the List deadline | LIST-BULK-UNIT store order, count and complete state |
| STORE-TYPE | Treat a wrong key type as a missing List | LIST-BULK-UNIT store wrong type |
| INTERPRETER-DIRECTION | Exchange the two push directions | LIST-BULK-UNIT interpreter order, count and complete state |
| INTERPRETER-ARGS | Drop the tail while interpreting | LIST-BULK-UNIT interpreter order, count and complete state |
| INTERPRETER-STATE | Discard the complete store after the push | LIST-BULK-UNIT interpreter order, count and complete state |
| LUA-DIRECTION | Exchange LPUSH and RPUSH | TWIN list order mismatch |
| LUA-LAST | Replace the final value | TWIN list order mismatch |
| LUA-HEADS | Replace each preceding value | TWIN list order mismatch |
| LUA-ARGUMENT-ORDER | Reverse the flattened argument spine | TWIN list order mismatch |
| READONLY | Classify both pushes as reads | LIST-BULK write classification |
| TWIN-ARGS | Forward only two values to the twin | TWIN list length mismatch |
| TWIN-DIRECTION | Exchange insertion ends in the twin | TWIN list order mismatch |
| TWIN-DROP | Insert only the first value in the twin | TWIN list length mismatch |

Controls cover 40 unit scenarios and the left, right, within-script,
cross-script and computed-argument probes. The argument-order fixture
contains duplicates and a non-palindromic sequence of constructor heads.

The focused capture `run-rsWxMp` under
`/Users/oobi/Documents/gpt18/tether-m1-list-bulk/.kanon-exec/` records:

```text
PASS LIST-BULK-MUTATIONS killed=16 survived=0 restored=6
```

No inherited mutation assertion or trusted-source bound changed.

The final continuation capture `run-yVZLJB` in the same directory repeats
`PASS LIST-BULK-MUTATIONS killed=16 survived=0 restored=6` on the final
source tree. It completes the nine components left unfinished by the
external timeout of `run-QPhjp8`; the M0 timing failure remains open.

## M1 Set bulk changes, 2026-09-17

`python3 -P dev/set-bulk-mutations.py` compiled and killed all 16 mutants
and reran six restored controls. The focused capture is
`/Users/oobi/Documents/gpt18/tether-m1-set-bulk/.kanon-exec/run-0VxT6F`.

| Mutation | Required failure |
| --- | --- |
| STORE-DUPLICATES | Distinct count and complete store state |
| STORE-DROP | Missing requested members in complete state |
| STORE-FIRST | Changed first member in complete state |
| STORE-EXPIRY | Lost expiry in complete state |
| STORE-EMPTY | Empty key retained after removing the final member |
| STORE-TYPE | Wrong-type store operation accepted |
| INTERPRETER-DIRECTION | Add and remove dispatch reversed |
| INTERPRETER-ARGS | Interpreter drops the remaining members |
| INTERPRETER-STATE | Interpreter drops unrelated state |
| LUA-COMMAND | Lua dispatch selects the wrong Redis command |
| LUA-LAST | Terminal member lost in the emitted command |
| LUA-HEADS | Earlier members lost in the emitted command |
| READONLY | Write command classified as read-only |
| TWIN-ARGS | Independent twin drops the remaining members |
| TWIN-ADD-COUNT | Duplicate additions counted more than once |
| TWIN-REMOVE-COUNT | Missing or duplicate removals counted |

Every mutant must build and fail its assigned assertion. Restored controls
cover the 44 unit scenarios plus add, remove, within-script retention,
cross-invocation retention and computed member arguments. Each probe
requires a nonempty scenario list.

```text
PASS SET-BULK-MUTATIONS killed=16 survived=0 restored=6
```

All inherited mutation assertions and trusted-source bounds remain in place.

## M1 Hash field deletion, 2026-09-18

`python3 -P dev/hdel-many-mutations.py` checks 14 compiling mutations
against assertions about the command's observable behavior. The runner
works in a temporary copy, restores each edited file and rebuilds before
rerunning the five named controls. Its summary counts observed control
markers and requires the complete control inventory.

| Mutation | Required failure |
| --- | --- |
| STORE-DUPLICATES | Missing or duplicate fields counted as removals |
| STORE-TAIL | Remaining requested fields omitted |
| STORE-FIRST | First requested field changed |
| STORE-EXPIRY | Nonempty Hash loses its expiry |
| STORE-EMPTY | Empty Hash key retained |
| STORE-TYPE | Wrong-type store operation accepted |
| INTERPRETER-ARGS | Interpreter drops remaining fields |
| INTERPRETER-STATE | Interpreter drops unrelated state |
| LUA-COMMAND | Lua dispatch selects HEXISTS instead of HDEL |
| LUA-LAST | Terminal field lost in the emitted command |
| LUA-HEADS | Earlier fields lost in the emitted command |
| READONLY | Write command classified as read-only |
| TWIN-ARGS | Independent twin drops remaining fields |
| TWIN-COUNT | Independent twin counts missing or duplicate fields |

The controls cover the 36 unit scenarios, the eight-case deletion probe,
within-script retention, cross-invocation retention and computed arguments.
Every probe requires a nonempty scenario list. The scoped run captured in
`run-QwVt8A` reports:

```text
PASS HDEL-MANY-MUTATIONS killed=14 survived=0 restored=5
```

The complete ladder in `run-h0yezK` repeats the same successful mutation
summary. Its full-stream audit verifies all 26 inherited and new mutation
summaries. The full ladder stays red solely for the open M0 timing gate.

All inherited mutation assertions, trusted-source bounds and the 150 ms
M0 timing bound remain in place.

## 2026-09-18 M1 Hash field/value writes

The `dev/hset-many-mutations.py` runner compiles each mutant in an
isolated copy and requires its named semantic assertion to fail.
Compilation failures and missing or ambiguous anchors cannot count as
kills. The runner restores each source file in `finally`, rebuilds, and
requires all six exact control markers after the final restoration.

| Mutation | Required detector |
| --- | --- |
| STORE-DUPLICATES | Distinct new-field count and complete state |
| STORE-TAIL | Remaining pairs are applied |
| STORE-FIRST | The first field and value are retained |
| STORE-ORDER | The last repeated field wins |
| STORE-EXPIRY | Complete state includes the existing expiry |
| STORE-TYPE | Wrong types refuse without writes |
| INTERPRETER-ARGS | The interpreter passes all remaining pairs |
| INTERPRETER-PAIR | Field and value positions stay distinct |
| INTERPRETER-STATE | Returned state retains unrelated data |
| LUA-COMMAND | HSET writes the complete expected Hash |
| LUA-LAST | The final pair's value is preserved |
| LUA-HEADS | Computed fields and values keep their positions |
| LUA-FLATTEN | Iterative lowering preserves all 129 pairs |
| READONLY | Tag 58 always uses write dispatch |
| TWIN-ARGS | The independent twin applies every pair |
| TWIN-COUNT | Repeated and existing fields do not inflate counts |

Controls are the 43-case unit suite, a nine-case write probe,
three 129-pair cases, and one case each for computed operands,
within-Script retention and cross-invocation retention. The older
HSET-COUNT mutation retains its overwrite-count assertion while its
anchor follows the shared HSET implementation. HMGET's INTERPRETER-ARGS
anchor follows the shared argument decoder and still swaps the first
two arguments. Its reply-and-complete-state assertion is unchanged.
Earlier records are unchanged.

The first full ladder capture, `run-hjThUQ`, exposed a stale HMGET
INTERPRETER-ARGS anchor and five stale scalar-state detector markers in
the new suite. The HMGET anchor now targets the generic decoder's
`Ok (first, next :: rest)` expression. The HSET markers now pin the
actual Hash-state assertions. The initial failures remain in their
capture; they are not counted as successful kills.

The corrected complete runners report:

```text
PASS HSET-MANY-MUTATIONS killed=16 survived=0 restored=6
PASS HMGET-MUTATIONS killed=16 survived=0 restored=6
```

Evidence is retained under
`/Users/oobi/Documents/gpt18/tether-m1-hset-many/.kanon-exec/`:
`run-pKXzlo` for HSET and `run-LOcPwk` for HMGET. Both exit 0 with empty
stderr, 16 named kills and all six controls restored. The full-stream
audit `run-Gb8dfw` verifies these alongside every earlier slice's required
rows and all 27 mutation summaries. The independent 150 ms M0 timing
gate remains open at a measured median of 293.206 ms.

The review round of 2026-09-18 renames the twin HSET argument table from
`pairs` to `items` and refuses an odd argument count. The TWIN-ARGS and
TWIN-COUNT anchors follow the new names. Both detectors are unchanged.
The unit control is the 43-case suite, which adds the empty tag 1
`mu<BulkPairs>` payload.

## M1 conditional Hash writes and byte lengths (2026-09-18)

`dev/hash-conditional-mutations.py` builds each source mutant in a private
copy and requires its named failed assertion. Thirteen distinct mutations
and three restored controls are pinned by both the runner and the slice
driver. The author's run `run-sEP73E` in the isolated work directory's
`.kanon-exec` records exit 0 for the first twelve of them and:

```text
PASS HASH-CONDITIONAL-MUTATIONS killed=12 survived=0 restored=3
```

| Mutation | Required detector |
| --- | --- |
| STORE-OVERWRITE | Conditional insertion preserves existing fields and complete state |
| STORE-NOOP-COUNT | An existing field returns 0 |
| STORE-NOOP-EXPIRY | A refused overwrite retains its deadline |
| STORE-LENGTH | Byte lengths match the explicit unit cases |
| INTERPRETER-NX | Tag 59 uses conditional insertion |
| INTERPRETER-LENGTH | Tag 60 returns byte length |
| LUA-OVERWRITE | The independent twin reports a Hash field mismatch |
| LUA-LENGTH | The generated Lua returns the expected length |
| LUA-DISPATCH-BOUND | The length probe stops in `out-length/body-0.lua` |
| READONLY-LENGTH | HSTRLEN retains its no-writes header |
| READONLY-INSERT | HSETNX never receives a no-writes header |
| TWIN-OVERWRITE | The twin preserves an existing field |
| TWIN-LENGTH | The twin returns the expected byte length |

Restored controls are the 32-scenario unit suite, seven insertion probes
and nine length probes. The first run expected a reply mismatch for the
two overwrite mutations, but the stronger complete-state check failed
earlier. Both markers now pin `TWIN hash field mismatch`; the complete
rerun killed those twelve mutations with no survivors. The review round
adds `LUA-DISPATCH-BOUND` for the new tag 60 dispatch bounds of
`print/lua.ml`, and re-anchors `STORE-OVERWRITE` on the rest-aware `nx`
guard of `hset`. Assertions are unchanged.
The existing HSET-MANY STORE-TYPE source anchor follows HSET's optional
`nx` argument and retains its original wrong-type detector.

## M1 conditional List pushes, 2026-09-18

`python3 -P dev/list-conditional-mutations.py` compiles every mutation
and requires exit 1 at its named behavioral assertion. The completed
run reports `PASS LIST-CONDITIONAL-MUTATIONS killed=18 survived=0 restored=5`.

| Mutation | Detector |
| --- | --- |
| STORE-CREATE | Missing queues stay absent with count 0 |
| STORE-MISSING-COUNT | Complete-state unit cases pin the zero reply |
| STORE-EXPIRY | Existing List deadlines survive a successful push |
| INTERPRETER-SINGLE-X | Scalar tags retain the existence condition |
| INTERPRETER-BULK-X | Bulk tags retain the existence condition |
| INTERPRETER-SINGLE-DIRECTION | Scalar tags preserve the complete List order |
| INTERPRETER-BULK-DIRECTION | Bulk tags preserve the complete List order |
| LUA-LEFT-X | LPUSHX leaves a missing key absent |
| LUA-RIGHT-X | RPUSHX leaves a missing key absent |
| LUA-BULK-LEFT-X | Bulk LPUSHX leaves a missing key absent |
| LUA-BULK-RIGHT-X | Bulk RPUSHX leaves a missing key absent |
| LUA-SINGLE-DIRECTION | The twin detects incorrect scalar insertion order |
| LUA-BULK-DIRECTION | The twin detects incorrect bulk insertion order |
| LUA-LAST | The twin detects a dropped final bulk argument |
| READONLY-SINGLE | LPUSHX never receives a no-writes header |
| READONLY-BULK | Bulk LPUSHX never receives a no-writes header |
| TWIN-CREATE | The independent twin must preserve a missing key |
| TWIN-DIRECTION | The independent twin must preserve insertion order |

Controls are the 74-case unit suite and one six-case probe for each of
`left`, `right`, `leftBulk` and `rightBulk`, run before mutations and
after restoration. Every mutation was killed by its intended assertion.
The older List, bulk List, bulk Set and bulk Hash deletion mutation
anchors follow the new shared command table and optional `xx` argument.
Their mutation counts and failure assertions remain unchanged.

## 2026-09-19: M1 List removal

`python3 -P dev/list-remove-mutations.py` passed with
`PASS LIST-REMOVE-MUTATIONS killed=14 survived=0 restored=5` in the
corrected focused capture `.kanon-exec/run-bcfByX`. Every mutant compiled
before its semantic probe ran. The runner restores each source in a
`finally` block, rebuilds, and repeats all five controls.

| Mutant | Assertion |
| --- | --- |
| STORE-ZERO | Zero removes every matching value |
| STORE-DIRECTION | Positive and negative counts select opposite ends |
| STORE-MATCH | Only byte-equal values are removed |
| STORE-EMPTY | Removing the final item deletes the key |
| STORE-EXPIRY | A remaining List keeps its expiry |
| STORE-PRECEDENCE | Count validation precedes key type checks |
| STORE-MINIMUM | The minimum signed value returns Redis's range error |
| INTERPRETER-TAG | Script tag 65 dispatches to LREM |
| LUA-COUNT | Emitted Lua preserves the requested limit |
| LUA-VALUE | Emitted Lua preserves the requested byte value |
| LUA-DIRECTION | Emitted Lua preserves the count's sign |
| READONLY | LREM never receives a no-writes header |
| TWIN-DIRECTION | The independent twin selects the correct end |
| TWIN-ZERO | The independent twin removes every match at zero |

Controls are the 135-case unit suite, seven-case `head`, `tail` and
`all` probes, and a binary probe. The initial twin-direction mutant
changed parsing as well as direction and failed a different assertion;
the final mutant changes only the starting index and is killed by the
intended order assertion. The 302 statically discovered mutation anchors
across all suites match exactly once. Existing inventories are unchanged.

## 2026-09-19: M1 List insertion

The new runner is `dev/list-insert-mutations.py`, included in
`dev/m1-list-insert.sh`. It mutates disposable source copies, compiles
each mutation and requires the designated semantic failure. Its inventory
is 14 killed, zero surviving and five restored controls.

| Mutation | Required detection |
| --- | --- |
| STORE-SIDE | BEFORE and AFTER placement differ |
| STORE-PIVOT | Only equal byte pivots match |
| STORE-PREFIX | A multi-item prefix retains its order |
| STORE-COUNT | The reply is the new length |
| STORE-MISSING | An absent key returns zero |
| STORE-NO-PIVOT | A missing pivot returns minus one |
| STORE-EXPIRY | Insertion preserves the full deadline map |
| INTERP-SIDE | Script tags dispatch to the correct side |
| LUA-SIDE | Printed commands preserve insertion direction |
| LUA-OPERANDS | Printed pivot and value positions are correct |
| WRITE-FLAG | LINSERT bodies cannot be classified as read-only |
| TWIN-SIDE | The independent twin preserves insertion direction |
| TWIN-MISSING | The twin returns zero for an absent key |
| TWIN-NO-PIVOT | The twin returns minus one for a missing pivot |

The five restored controls are the 50-case unit executable and the
before, after, binaryBefore and computedAfter probes. The successful
scoped capture is `gpt18/tether-m1-list-insert/.kanon-exec/run-JLerlM`;
all intended assertions failed on their mutants, and all restored
controls passed. The wrapper's later PATH-only HOUSE failure is explained
in the build log. Across the complete repository, 316 statically found
mutation anchors match exactly once. Earlier mutation inventories and
timing bounds remain unchanged.

## 2026-09-20: M1 atomic List moves

`python3 -P dev/list-move-mutations.py` builds each altered implementation
before requiring its intended assertion to fail. All 14 mutants were
killed; five controls passed before mutation and after restoration.

The store mutants swap either endpoint, duplicate destination contents,
retain an empty source, discard an aliased or destination expiry,
ignore a destination type error, and replace nil with empty bytes.
Interpreter mutants swap endpoint decoding or argument order. Lua
mutants change the source endpoint, alias the destination, or classify
LMOVE as read-only. The independent twin mutant pops the wrong end.

The existing LRANGE error-tag mutation now matches the joined decoder
line. Its changed reply tag and required failure marker are unchanged.
No inherited mutation or assertion was removed.

A focused run compiled the adapted `LUA-ERR-TAG` mutation, killed it at
its intended reply-kind assertion, then rebuilt and passed the restored
control. It exited zero with
`PASS LIST-MOVE-LEGACY-MUTATION name=LUA-ERR-TAG killed=1 restored=1`.
Its capture is `run-yKbF0J` beside the evidence below. A separate static
audit found all 330 literal mutation anchors present exactly once.

Evidence: `/Users/oobi/Documents/gpt18/tether-m1-list-move/.kanon-exec/run-ehrO22/command-0001.stdout`.

```text
PASS LIST-MOVE-MUTATIONS killed=14 survived=0 restored=5
```
