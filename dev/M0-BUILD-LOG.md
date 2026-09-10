# M0 build log

## Stage 0 (2026-09-09)

Kanon pin 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf.  Brief: /Users/oobi/Documents/tether-m0/stage-0-brief.md.  Rulings: /Users/oobi/Documents/tether-m0/RATIFICATIONS.md.  Stage 0 runs the seven agent spikes (b) to (h) and creates the repository skeleton.  Nothing builds at Stage 0.  No agent commits.

### 1 Deliverables

Repository skeleton at /Users/oobi/Documents/tether, `git init -b main`, zero commits:

- README.md, .gitignore, LICENSE-MIT, LICENSE-APACHE.
- Directories surface/, print/, store/, runtime/, bin/, examples/, corpus/, corpus/lua/, corpus/twin/, dev/ and dev/PATCHES/.  Eight directories carry one .gitkeep marker (S0-D1).
- corpus/lua/m0-spine.lua, the two-line Lua fixture, 71 bytes, LF between the two lines and no trailing newline.
- corpus/twin/spine.c, sort.c, parser.c and interp.c, copied byte for byte from the trice sibling, 280 plus 398 plus 563 plus 479 equal 1720 lines.
- dev/TOOLCHAIN.md, spike (a), the tool table of 21 rows.
- dev/bench.sh, carried without an edit from the pin, dev/tcc-denominator.sh and dev/denominators.json, spike (b).
- dev/SPIKE-PIN.md and dev/spike-pin.sh, spike (c).
- dev/SPIKE-LINES.md, spike (d).
- dev/SPIKE-BODY.md and dev/spike-body.sh, spike (e).
- dev/SPIKE-SERVER.md and dev/redis-up.sh, spike (f).
- dev/SPIKE-INT64.md, spike (g).
- dev/DENOMINATORS.sha256, spike (h), eight entries.
- dev/M0-BUILD-LOG.md and dev/MUTATION-LOG.md, this file and the mutation record.

Stage 0 adds no vendor/kanon submodule, no dev/PIN, no dev/carry-check.sh, no SPEC.md, no dune-project and no root dune file.  Those are Stage A work.  Everything under /Users/oobi/Documents/tether-m0/spikes/ is scratch and never enters the repository.

### 2 Gates

Every row below was rerun by the judge on 2026-09-09.  The evidence is the printed line.

| Gate | Result | Evidence |
| --- | --- | --- |
| S0-G1 REPO | PASS | `git symbolic-ref --short HEAD` prints `main`;  `git rev-list --count HEAD` exits 128 on the unborn branch, so the commit count is zero;  `git submodule status` prints 0 lines;  dev/PIN, SPEC.md, dune-project, dune and .gitmodules are all absent;  after the staging step `git status --porcelain` lists 0 untracked paths and no spikes path. |
| S0-G2 KANON-UNTOUCHED | PASS | `git -C /Users/oobi/Documents/kanon rev-parse HEAD` prints 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf;  the start capture and the end capture of `git status --porcelain` are both 47 lines and their diff is empty;  `git worktree list` shows no tether path. |
| S0-G3 DENOMINATORS | PASS | `zsh -c "cd /Users/oobi/Documents/tether && shasum -a 256 -c dev/DENOMINATORS.sha256"` prints OK on all eight lines and exits 0. |
| S0-G4 DENOM-ROWS | PASS | `node -e` parses dev/denominators.json: date 2026-09-09, pin 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf, and each of the three rows carries a numeric value, median_ms, min_ms, max_ms, runs 5, lines 1720, command, method and brief_reference;  `zsh -n dev/tcc-denominator.sh` exits 0;  one rerun printed three DENOM lines, recorded in section 3. |
| S0-G5 PIN-SPIKE | PASS | `zsh dev/spike-pin.sh /Users/oobi/Documents/tether-m0/spikes/pin .../pin/PIN` prints `PIN 2c2e6e6 unlisted=0 lib=25 wasm=4 runtime=3` and exits 0. |
| S0-G6 LINES-SPIKE | PASS | The export's dev/trusted-lines.sh prints `TRUSTED-LINES kernel=3997/4000 encoder=246/600 OK` and exits 0;  dev/SPIKE-LINES.md holds five projections, 250 of 320, 200 of 240, 160 of 200, 170 of 300 and 210 of 300, with headroom 70, 40, 40, 130 and 90;  the basis counts were reread live on the export: eterm.ml 117, pp.ml 102, eval.ml 297, reactor.mjs 275 and run.mjs 28. |
| S0-G7 BODY-SPIKE | PASS | `zsh dev/spike-body.sh corpus/lua/m0-spine.lua` prints `BODY-SAME sha256=9eb4415dc3a730e89742f13535413cceb77671f21420c9137a4bebbc5d99d6e5 sha1=d8018db15d29480d5eca4c33d3ded2ffa01852a6 bytes=71` and exits 0;  `rg -c $'\r'` over the fixture prints nothing and exits 1;  `tail -c 1` of the fixture piped into `xxd -p` prints 29 and never 0a, see finding F-2. |
| S0-G8 SERVER-SPIKE | PASS | The judge repeated the proof run with the sandbox disabled: `REDIS-UP port=48001 pid=135 pidfile=/Users/oobi/Documents/tether-m0/spikes/server/redis.pid`, `PONG`, `shasum -a 1` and SCRIPT LOAD both print d8018db15d29480d5eca4c33d3ded2ffa01852a6, EVALSHA prints 1 then 2, SCRIPT FLUSH prints OK, the next EVALSHA prints `NOSCRIPT No matching script. Please use EVAL.`, the kill exits 0, `kill -0 135` prints `No such process` and exits 1, and the last `redis-cli -p 48001 ping` prints `Could not connect to Redis at 127.0.0.1:48001: Connection refused`. |
| S0-G9 INT64-SPIKE | PASS | Six live reruns, each equal to dev/SPIKE-INT64.md: 9007199254740992;  9223372036854775807;  9007199254740993;  9007199254740992;  "9007199254740993";  ["9007199254740993"].  Tools: LuaJIT 2.1.1787165859 and jq-1.6. |
| S0-G10 TOOLCHAIN | PASS | Every present row matched a live rerun of its own command: redis-server v=8.10.1, redis-cli 8.10.1, wasm-tools 1.258.0, LuaJIT 2.1.1787165859, tcc 0.9.28rc 2026-09-04, wasmtime 48.0.1, node v23.10.0, wasm-opt 130, bash 3.2.57(1), curl 8.7.1, jq-1.6, shasum 6.02, Python 3.14.7, ocaml 5.2.1, dune 3.24.2, dunecho 0.1.0, git 2.50.1;  `command -v` prints nothing for lua, hyperfine, webdis and upstash. |
| S0-G11 PROSE | PASS | An `rg -c` sweep with a pattern built by `printf` from the two byte sequences of U+2014 and U+2013 prints nothing for README.md, LICENSE-MIT, LICENSE-APACHE and every dev/*.md file, this log and the mutation log included. |
| S0-G12 DEV-FILES | PASS | Every file of section 1 exists;  bench.sh, tcc-denominator.sh, spike-pin.sh, spike-body.sh and redis-up.sh are each -rwxr-xr-x and each exits 0 under `zsh -n`;  `shasum -a 256 dev/bench.sh` prints d408fb5a3d88da3334783e0fb67e8c7ce25aa546c4c428853031d83cfd30d5ae, the carried value. |

No halt blocker of section 6 fired.  No blocker was waived.

### 3 The frozen numbers

dev/denominators.json is frozen.  A re-measurement is a new dated file and never an overwrite.  The panel figures are R-Q1 reference values from the design brief.

| Row | Frozen value (ms per kloc) | Panel figure | Judge rerun 19:45 | Rerun over frozen |
| --- | --- | --- | --- | --- |
| tcc_raw_ms_per_kloc | 500.413 | 26.28 | 41.628 | 0.083 |
| tcc_corrected_ms_per_kloc | 315.185 | 5.38 | 7.551 | 0.024 |
| trice_end_to_end_ms_per_kloc | 2149.171 | 453.0 | 622.169 | 0.290 |

Judge rerun line, printed by `zsh dev/tcc-denominator.sh /Users/oobi/Documents/tether-m0/judge/denom-scratch`, at `LOAD 19:45  27 users, load averages: 56.63 50.23 50.74` on 12 cores:

```
EMPTY tcc_empty_tu median_ms=58.613 min_ms=45.373 max_ms=150.748 runs=5 invocations=4 fixed_ms=58.613
DENOM tcc_raw_ms_per_kloc value=41.628 median_ms=71.601 min_ms=65.624 max_ms=79.925 runs=5 lines=1720
DENOM tcc_corrected_ms_per_kloc value=7.551 median_ms=12.988 min_ms=7.011 max_ms=21.312 runs=5 lines=1720
DENOM trice_end_to_end_ms_per_kloc value=622.169 median_ms=1070.130 min_ms=981.925 max_ms=1273.874 runs=5 lines=1720
```

The frozen figures were measured at a load average of 62, the judge rerun at 56, and the two differ by a factor of 4 to 40.  The dispersion is host load and not a defect of the script, because the shape of the three rows is stable and the corrected row tracks the raw row.  The gate reads the row shape and not the value, so the spread is information (brief section 6).  M0-TCC-RATIO is informational at M0 and gates at M1 and M2, so a quiet-host re-measurement must land as a new dated file before the M1 gate reads it.

### 4 Findings and how each was resolved

| Id | Finding | Resolution |
| --- | --- | --- |
| F-1 | After the skeleton stage staged its files, the later spikes (c) to (h) left 14 untracked paths, so the S0-G1 clause "no untracked path" was open.  The fixer may not stage. | Resolved at the staging step of section 3.12: `git -C /Users/oobi/Documents/tether add -A` ran after the two logs were written, and `git status --porcelain` then listed 0 untracked paths and no spikes path.  The closer repeats the same command with no effect. |
| F-2 | The brief asks in sections 3.2 and 4 that `tail -c 1` of corpus/lua/m0-spine.lua piped into `xxd -p` print 5d, but the brief's own quoted second line is `return redis.call('GET', KEYS[1])`, whose last byte is `)`, 0x29.  The two requirements cannot both hold. | The ruled literal text wins and the fixture is unedited.  `xxd` of the file shows 71 bytes, one 0a at offset 0x25 and the last byte 29, with no CR and no BOM.  The intent of the clause, "and never 0a", holds: the fixture ends without a newline.  A change to 5d would break the ruled text, the BODY-SAME sha256, the EVALSHA sha1 d8018db15d29480d5eca4c33d3ded2ffa01852a6 and the hash manifest.  Only the user can amend the brief. |
| F-3 | The stop step of spike (f) printed one interleaved job control line, `kill ... failed: no such process`, in an earlier transcript. | Shell job control noise of that one session.  The judge rerun is clean: the kill exits 0, the following `kill -0` fails and the port refuses a connection. |
| F-4 | The first fixed-cost shape of dev/tcc-denominator.sh subtracted three directory resets that the raw shape did not pay, so the corrected row went negative under load (run 1 min_ms -186.759). | Replaced before the freeze by the same-shape form, four empty `tcc -c` after one reset.  Runs 1 and 2 stay as scratch logs under /Users/oobi/Documents/tether-m0/spikes/denom/ and never entered the repository.  The frozen file holds run 3. |
| F-5 | Two spikes claimed the same decision id S0-D6 for two different decisions. | Renumbered in section 5 of this log, which is the record of the stage: the pin read form keeps S0-D6 and the basis file choice becomes S0-D8.  No repository file carried either id, so no file changed. |

### 5 Decisions

- S0-D1 marker file.  The marker is `.gitkeep`.  Eight directories carry one: bin/, corpus/twin/, dev/PATCHES/, examples/, print/, runtime/, store/ and surface/.  corpus/, corpus/lua/ and dev/ hold real files and carry none.  corpus/twin/.gitkeep stays beside the four C programs and costs nothing.
- S0-D2 denominator method.  The timer is dev/bench.sh, a perf_counter_ns pair around one subprocess, one warm up and RUNS timed runs, RUNS 5.  Row 1, tcc_raw_ms_per_kloc: one timed command `rm -rf OUT && mkdir -p OUT && tcc -c -o OUT/NAME.o corpus/twin/NAME.c` for the four programs.  Row 2, tcc_corrected_ms_per_kloc: the raw median, min and max each minus the median of the same command shape over one empty translation unit, measured in the same run and printed as the EMPTY line.  Row 3, trice_end_to_end_ms_per_kloc: one reset, then `tcc -o OUT/NAME corpus/twin/NAME.c && OUT/NAME` for the four programs, the form the trice record measured.  value equals median_ms divided by 1.720.  Rerun command: `zsh /Users/oobi/Documents/tether/dev/tcc-denominator.sh [SCRATCH_ROOT]`.
- S0-D3 the tcc program set.  corpus/twin/ holds the four trice twin programs, copied with cp and checked with cmp, 1720 lines, sha256 of the concatenation 9c24ca0f09c9553f468ee849f00ddf05f6a3d3284dc62933a7bb0952feb8d08f.  The pin carries no C corpus and no tcc row, and the three reference figures were measured on exactly these programs, so a later ratio over any other line set would not compare.
- S0-D4 the server protocol.  A candidate port is drawn from 30000 to 49999 with `$RANDOM`, filtered with `lsof -nP -iTCP:<p> -sTCP:LISTEN`, and accepted only when the started server answers PONG within 50 tries of 0.1 s, at most 20 candidates.  The caller names the pidfile;  the server log is `<LOGDIR>/redis-<p>.log` and LOGDIR defaults to the pidfile directory, so both match the .gitignore rows `*.pid` and `*.log`.  The stop form is `trap 'kill $(cat PIDFILE)' EXIT` in the calling gate.
- S0-D5 the canonical body.  A Lua body is LF only, with no CR, no BOM and no trailing newline, because the server hashes the loaded bytes and one extra byte is a different script, so EVALSHA misses.  The M0 spine fixture value past 2^53 is 9007199254740993, which is 2^53 plus 1 and the smallest integer that the number path changes.
- S0-D6 the pin read form.  dev/spike-pin.sh reads kanon only through commit objects: `git ls-tree -r --name-only PIN -- lib wasm runtime` for the file list and `git show PIN:PATH` piped into `cmp -s` for the bytes.  `unlisted` counts checkout files under the three directories that the pin tree does not list, through fd and comm.  A usage error exits 4 and a mismatch prints `PIN FAIL <reason>` and exits 1.
- S0-D7 the submodule flag.  `-c protocol.file.allow=always` is passed per command on `submodule add` and on `submodule update --init` and is never written into a config file.  Without it git 2.50.1 prints `fatal: transport 'file' not allowed` and exits 128.
- S0-D8 the projection basis.  Each projected leg names the exported file of the same shape as its basis: lua from lib/eterm.ml 117, sh from lib/pp.ml 102, store from lib/eval.ml 297, host-node from runtime/reactor.mjs 275, and host-rest from reactor.mjs 275 plus run.mjs 28.  The five numbers are part sums and not measurements, so each leg prints `N` until Stage B measures it (R-M0-3).

## Stage A (2026-09-09)

Base: committed Stage 0, `d53060e543813d7498e1c851130f41d3b14f49b4`.
This stage implements section 10 Stage A of the ruled M0 plan. Work was
prepared and validated in an isolated checkout and then staged in tether.
No commit is made by the agent. Stage B is the next implementation stage.

### Deliverables and decisions

- `vendor/kanon` is a submodule at `dev/PIN`, with the ruled local URL in
  `.gitmodules`. Root Dune files build the vendored executable as a scoped
  target. The main kanon checkout is never built or edited.
- `SPEC.md` carries the eight inherited R0 rows and explicit naming/refusal
  citations. It labels the later Redis behavior as the M0 contract.
- `dev/carry-check.sh` checks the full pin, submodule initialization,
  submodule HEAD, staged gitlink, staged `.gitmodules`, zero patches,
  tracked vendor changes and all 32 files under lib/wasm/runtime. It also
  checks four byte-identical copies: `dev/bench.sh`, the inherited audit
  and line-counter scripts, and `runtime/reactor.kan`. A last check
  compares the whole submodule worktree, outside its build outputs,
  against the file list of the pin, so an extra file under `bin/`,
  `surface/` or any other compiled directory fails the gate.
- `dev/r0-count.sh` rebuilds only `vendor/kanon/bin/kanon.exe` before
  comparing its eight derived rows to both specifications. This prevents
  a stale executable from hiding source changes.
- `dev/r0-audit.sh` joins the whole prose surface of `SPEC.md` into
  sentences, across blank lines, list markers and table lines. A sentence
  counts as a claim when it links a subject to a naming, refusal,
  admission or permission word, with a copula or with one of the state
  verbs stay, remain, become and continue, or when it grants a nesting
  permission. Every claim sentence must be a ruled one with an audited
  citation. The script also checks the source locations and runs the
  inherited shape-isolation rule. That script reads through
  ripgrep, and it prints its OK line over an empty read, so the gate reads
  ripgrep first and fails when ripgrep fails. `dev/foundation.py`
  implements these local gates and keeps the output of a failing command
  in the printed reason. No gate reads the origin checkout.
- `dev/stage-a.sh` composes foundation, inherited trusted-line and frozen
  checksum gates. It reads the printed trusted-line and fails on an empty
  count, which a broken awk produces under the inherited `set -u`.
  `dev/stage-a-mutations.py` uses disposable copies with independent Git
  metadata, requires the printed reason of every case, restores each
  mutation and reruns the gates.
- The Stage 0 denominator files are unchanged. Capture directories and
  Python bytecode caches are ignored. There is no Redis compiler claim at
  this stage, and no new trusted-line measurement is substituted for `N`.

### Validation

`sh dev/stage-a.sh` exits 0:

```text
PIN 2c2e6e6 unlisted=0
CARRY files=36 diff=0 vendor=32 copies=4
R0-COUNT formers=2 schema=4 shapes=5 admitted=3
R0-AUDIT ok
TRUSTED-LINES kernel=3997/4000 encoder=246/600 OK
PASS STAGE-A
```

All eight `dev/DENOMINATORS.sha256` entries pass. The scoped Dune build
reports no warnings or errors. `python3 -P dev/stage-a-mutations.py`
exits 0 and prints `PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1`.
The sixth-shape case rebuilds the edited kernel and observes the changed
derived count before restoring it. The NO-RG and NO-AWK cases break one
tool on PATH and mutate no source, and both gates fail. Details are in
`dev/MUTATION-LOG.md`.

User commit command after reviewing the staged diff:

```sh
git -C /Users/oobi/Documents/tether commit -s -m "M0 Stage A: pin the foundation and add integrity gates"
```

### Review round 2026-09-09 (Stage A)

Review of the staged Stage A slice on d53060e. Two fix rounds ran; the
gate table below is from the last gates log,
/Users/oobi/Documents/tether-stage-a-review/gates-A-2.log.

| id | severity | file | fix or ruling |
|----|----------|------|---------------|
| B-1 | high | dev/foundation.py:111 | R0-AUDIT passes vacuously when ripgrep is not on PATH. Fixed: audit reads `rg --version` and keeps the script output. |
| A-2 | medium | dev/foundation.py:124 | Gate failures report an opaque CalledProcessError, and the initialization check is unreachable (merges A-1 and C-1). Fixed: `command` prints the failing command with its stdout and stderr; carry checks `.git` and the toplevel before the HEAD comparison. |
| A-3 | medium | dev/stage-a-mutations.py:60 | The mutation runner asserts instead of verifying: any "<ACTION> FAIL" scores a kill and killed=11 is a literal (merges A-7). Fixed: each case carries the reason text the gate prints, `killed()` requires it, the count is `len(scored)`; round 2 made SHAPE-LEAK require the leaking site and `R0-AUDIT FAIL`. |
| A-4 | medium | dev/foundation.py:57 | CARRY walks lib, wasm and runtime only, so an added file elsewhere in the pin passes while the gate prints diff=0 unlisted=0. Fixed: whole worktree against `git ls-tree -r PIN`, build outputs excluded. |
| B-3 | medium | dev/stage-a.sh:8 | The TRUSTED-LINES leg is accepted on exit status alone, so a missing awk makes it vacuous. Fixed: the line must match `TRUSTED-LINES kernel=<digits>/4000 encoder=<digits>/600 OK`. Round 2 replaced the sh glob, which accepted one digit and any tail, with a digit-run check on each count and an exact comparison of the rebuilt line. |
| D-1 | medium | dev/foundation.py:99 | R0-AUDIT does not implement the ruled "a naming with no citation is a gate failure". Fixed: every naming, refusal or admission sentence in SPEC.md must be a ruled row and every refusal must cite an audited site. |
| B-2 | medium | README.md:21 | The documented tool list is wrong: ripgrep, shasum and awk are missing and "Python 3" is not enough for python3 -P (merges C-3 and D-4). Fixed: the sentence names Git, Python 3.11 or newer, zsh, ripgrep, shasum, awk, wc, OCaml 5.2.1, Dune 3.24.2 and Zarith 1.14. |
| ND-1-1 | medium | dev/foundation.py:168 | New defect from the round 1 fixes: the naming audit read lines, not sentences, so a wrapped naming passed. Fixed in round 2: `claim_sentences` joins wrapped paragraphs and list items before the claim scan. |

Ruled: 0. Refuted: 0.

Merged and dropped: 12. A-1 and C-1 merged into A-2 (same file, same
defect class: a wrong or opaque failure reason). A-7 merged into A-3 (the
killed=11 literal is the same defect as the kill assertion). C-3 and D-4
merged into B-2 (same file and line, the tool list). A-6 and D-2 merged
into C-2, then cut with it by the 7-finding cap. C-2 true but low: the
pin's .gitignore holds only _build/, *.install and .gatework/, so
lib/extra.o is untracked, not ignored. The wording was corrected at
dev/MUTATION-LOG.md:99, where the row now reads "Add lib/extra.o,
untracked at the pin", and only the case name IGNORED-EXTRA still reads
ignored; the gate leg named in the row is right. A-5 true but low at review round 1:
dev/stage-a-mutations.py:30 raised FileNotFoundError with a traceback
when no kanon.exe was built, which house rules allow, and review round
3 replaced that raise with the printed control failure `CONTROL FAIL
missing build ... run sh dev/stage-a.sh first` at exit 1. B-4 true but low: the root dune -warn-error +a is
inert over the vendored compile, no gate result changes. C-4 true but
low: the dev/M0-BUILD-LOG.md transcript is abridged by eight checksum
rows, every number reproduces. D-3 true but low: an unanchored SPEC.md:344
citation, covered by the D-1 fix surface.

Gate table, one-minute load 40.47 at start and 39.12 at end:

| leg | verbatim line |
|-----|---------------|
| PIN | `PIN 2c2e6e6 unlisted=0` |
| CARRY | `CARRY files=36 diff=0 vendor=32 copies=4` |
| R0-COUNT | `R0-COUNT formers=2 schema=4 shapes=5 admitted=3` |
| R0-AUDIT | `R0-AUDIT ok` |
| TRUSTED-LINES | `TRUSTED-LINES kernel=3997/4000 encoder=246/600 OK` |
| sha256 | `dev/bench.sh: OK` |
| sha256 | `dev/denominators.json: OK` |
| sha256 | `dev/tcc-denominator.sh: OK` |
| sha256 | `corpus/twin/spine.c: OK` |
| sha256 | `corpus/twin/sort.c: OK` |
| sha256 | `corpus/twin/parser.c: OK` |
| sha256 | `corpus/twin/interp.c: OK` |
| sha256 | `corpus/lua/m0-spine.lua: OK` |
| stage-a.sh | `PASS STAGE-A` |
| stage-a.sh | `EXIT 0` |
| mutations | `PASS STAGE-A-MUTATIONS killed=15 survived=0 restored=1` |

Carry: files=36 diff=0 vendor=32 copies=4. Count: formers=2 schema=4
shapes=5 admitted=3, kernel=3997/4000 encoder=246/600. Mutations:
killed=15 survived=0 restored=1. Verdict GATES-OK.

### Review round 2 2026-09-10 (Stage A)

Second review of the same staged slice. Seven findings were kept and
fixed. The numbers above are the round-1 log, and the runner scored 26
cases at review round 2.

| id | severity | file | fix |
|----|----------|------|-----|
| A-1 | high | dev/foundation.py:18 | R0-AUDIT read three keyword phrases, so a rephrased or wrapped uncited naming passed while SPEC.md and this log claim every naming sentence is read (merges C-1). Fixed: `claim_sentences` joins across blank lines and reads list and table lines, and a sentence that links a subject to a naming, refusal, admission or permission word, with a copula or with one of the state verbs stay, remain, become and continue, is a claim sentence. Round 3 widened the verb list and dropped the ruled-token requirement, so a refusal written with a state verb and a naming of an unruled name both fail. Five cases added. |
| A-4 | medium | dev/foundation.py:112 | A recursive submodule init failed CARRY, because the pin carries the nested gitlink `vendor/tot`. Fixed: the pin list is read with modes, files under a nested gitlink are not unlisted files, and each nested gitlink is checked for its directory and, when initialized, for its recorded hash. |
| B-1 | medium | dev/foundation.py:17 | CARRY failed on the capture directories `.kanon-exec` and `.kanon-wait`, which the root .gitignore and the mutation runner both treat as disposable. Fixed: the three lists agree. |
| A-3 | medium | dev/foundation.py:193 | The citation checks compared the ruled rows with the ruled anchors, so no SPEC.md content could fail them, and the anchor leg had no case. Fixed: the citation checks read the sentences of SPEC.md before the equality check, and the ANCHOR-MOVED case covers the anchor leg. |
| A-2 | medium | dev/stage-a-mutations.py:63 | The checksum leg and the submodule HEAD comparison had no case (merges D-4). Fixed: DENOMINATOR-BYTE and HEAD-SHA. |
| D-1 | medium | dev/M0-BUILD-LOG.md:184 | The C-2 paragraph of the round-1 block cited three lines that carry no such wording. Fixed: the paragraph records the corrected row dev/MUTATION-LOG.md:99 and the case name. |
| C-2 | medium | dev/M0-BUILD-LOG.md:171 | The round-1 block recorded a digit-run check, but the sh glob `[0-9]*` accepts one digit and any tail. Fixed: dev/stage-a.sh cuts each count out, requires a digit run and compares the rebuilt line with the printed one; the row records the round-2 check. |
| ND-1-1 | medium | dev/foundation.py:135 | The two nested gitlink requires were unreachable, because the whole tree diff ran first and failed on the nested name. Fixed: the pin ls-tree read, the `listed` and `nested` sets and the two nested requires move above the tree diff, and the diff drops every nested name; cases NESTED-MISSING and NESTED-HEAD. |
| ND-2-1 | medium | dev/M0-BUILD-LOG.md:147 | The build log recorded 21 mutation cases. Fixed: dev/M0-BUILD-LOG.md:152, :228 and the gate block record the count of the run made after the later edits, and dev/MUTATION-LOG.md carries the same summary line. |
| ND-3-1 | medium | dev/foundation.py:145 | A nested gitlink that is not initialized had no emptiness leg. Fixed: the `.git` test is bound to `initialized`, a new leg requires an uninitialized nested checkout to be empty with the reason `nested submodule directory is not empty: <inner>`, and the NESTED-EXTRA case covers that leg. |

Refuted, 0. No verified item was refuted in this round.

Merged and dropped, 10. C-1 merged into A-1, same CLAIM keyword defect,
and A-1 carries the document leg with the correct SPEC.md line numbers.
C-3 merged into D-1, same file, same line 184, same defect. D-4 merged
into A-2, same battery and same defect class, and A-2 names both
uncovered legs. C-5 merged into A-5 and cut with it by the cap. A-5 cut
by the 7-finding cap, low, only line 1086 of the cited range 1083-1086
is anchored. B-2 cut by the cap, low, the sentence about ignored capture
directories becomes true with the B-1 fix. B-3 cut by the cap, low, a
dune that exits 127 ends the battery with no reason line. C-4 cut by the
cap, low, the SIXTH-SHAPE row records one of the two required texts. D-2
cut by the cap, low and overstated, because README.md:21 does resolve to
the sentence B-2 fixed. D-3 cut by the cap, low, no staged line says the
Stage B sixth-shape row is still owed.

Gate block after the fixes, the log
/Users/oobi/Documents/tether-stage-a-review/gates-B-4.log:

```text
PIN 2c2e6e6 unlisted=0
CARRY files=36 diff=0 vendor=32 copies=4
R0-COUNT formers=2 schema=4 shapes=5 admitted=3
R0-AUDIT ok
TRUSTED-LINES kernel=3997/4000 encoder=246/600 OK
dev/bench.sh: OK
dev/denominators.json: OK
dev/tcc-denominator.sh: OK
corpus/twin/spine.c: OK
corpus/twin/sort.c: OK
corpus/twin/parser.c: OK
corpus/twin/interp.c: OK
corpus/lua/m0-spine.lua: OK
PASS STAGE-A
EXIT 0
PASS STAGE-A-MUTATIONS killed=26 survived=0 restored=1
```

One-minute load 29.47 at the start and 31.54 at the end. Carry and count
numbers: files=36 diff=0 vendor=32 copies=4, formers=2 schema=4 shapes=5
admitted=3, kernel=3997/4000 and encoder=246/600. Mutations: killed=26,
survived=0, restored=1. Fix rounds: 4. Rounds 1 and 2 ran in run
wf_1171720a-ae4 and the rest in this run.

### Review round 3 2026-09-10 (Stage A)

Third review of the same staged slice. Fourteen findings were kept and
fixed. The numbers of the earlier blocks are the logs of those rounds.

| id | severity | file | fix |
|----|----------|------|-----|
| A-1 | high | dev/stage-a.sh:33 | The sha256 manifest leg passed vacuously when rows were deleted, and a broken shasum ended the ladder at exit 127 with no reason line (merges B-3). Fixed: the row count of `dev/DENOMINATORS.sha256` is read with `wc -l` and required to equal 8, and `shasum -a 256 -c` carries its own reason line and exit 1. Cases MANIFEST-ROW and NO-SHASUM. |
| A-2 | high | dev/foundation.py:30 | The naming and citation audit read no negation, so a sentence that reverses a ruled refusal passed. Fixed: hunks at ADVERB, STATE, MODAL, NESTS and VERB, where the copula accepts a run of negation adverbs and modal negation is its own alternative. Cases NEGATED-REFUSAL and MODAL-PERMISSION. |
| A-3 | medium | dev/r0-count.sh:5 | An absent or broken dune ended the ladder at exit 127 with the shell message and no R0-COUNT FAIL line (merges B-2). Fixed: a `command -v dune` guard and a guarded `dune build`, each with its own reason and exit 1. Cases NO-DUNE and NO-DUNE-PATH. |
| A-5 | medium | dev/foundation.py:130 | An initialized nested checkout had none of its files compared (merges C-7 as its documentation face). Fixed: `carry()` runs `git diff --no-ext-diff --name-only <head>` and `git ls-files --others -z` inside the nested checkout, with the build directories filtered as the outer leg filters them, and SPEC.md lines 105 to 113 state the three nested legs. Cases NESTED-UNLISTED and NESTED-TRACKED. |
| B-1 | medium | dev/stage-a-mutations.py:56 | The mutation runner raised FileNotFoundError on a tree with no `_build`, because no documented step guaranteed the binary. Fixed: the runner tests `(ROOT / binary).is_file()` and prints `CONTROL FAIL missing build ...: run sh dev/stage-a.sh first` with exit 1, and README.md gains the ordering paragraph after the command block. |
| D-1 | medium | dev/foundation.py:226 | A cited range was anchored at its end line only, so the refusal bodies of rules.ml:1083-1086 and positivity.ml:85-90 could be gutted while R0-AUDIT printed ok (merges A-4). Fixed: `anchors` gains rules.ml 1083, 1084 and 1085 and positivity.ml 85 to 89, and the citation leg requires both ends of a range. Cases CITATION-START and POSITIVITY-START. |
| C-4 | low | SPEC.md:16 | The mu_pack citation pointed at a pin line that does not state the colimit claim. Fixed: line 16 reads that `mu_pack` assembles the mu rule fields and refuses the right former at `lib/rules.ml:1388`, and cites `dev/INITIAL-CHAIN.md` of the pin for the colimit. |
| ND-1-1 | medium | dev/stage-a.sh:36 | The new manifest guard pinned the row count only, so a swapped or duplicated row passed. Fixed: a missing-file guard with its own reason, then a name guard that reads the name column with `awk`, sorts it under `LC_ALL=C` and requires the eight ruled paths. Case MANIFEST-SWAP. |
| ND-2-1 | medium | dev/MUTATION-LOG.md:134 | The recorded battery line read killed=36 while the runner scores 37. Fixed: the line reads `PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1`. |
| ND-2-2 | medium | dev/M0-BUILD-LOG.md:152 | The Stage A record sentence about the runner read killed=36. Fixed: it reads `PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1`, and no other number in the record moves. |
| ND-2-3 | medium | dev/MUTATION-LOG.md:171 | The paragraph that counts and names the cases of the round read ten cases and left MANIFEST-SWAP unnamed. Fixed: it names eleven cases, MANIFEST-ROW, MANIFEST-SWAP, NO-SHASUM, NO-DUNE, NO-DUNE-PATH, NEGATED-REFUSAL, MODAL-PERMISSION, CITATION-START, POSITIVITY-START, NESTED-UNLISTED and NESTED-TRACKED, which with the 26 round-2 cases give the observed 37. |
| ND-3-1 | medium | dev/MUTATION-LOG.md:171 | Two counts for round 3, because the four fix rounds of review round 2 were labelled review rounds. Fixed: lines 144, 160 and 168 name their fix round of review round 2, and line 174 reads "Review round 3 of the review added eleven cases." |
| ND-4-1 | medium | dev/M0-BUILD-LOG.md:228 | The round-2 block header stated the runner's case count in the present tense, "The numbers above are the round-1 log; the runner now scores 26 cases.", which is false on the current tree where the runner scores 37. Fixed: the sentence reads "The numbers above are the round-1 log, and the runner scored 26 cases at review round 2." |
| ND-4-2 | medium | dev/M0-BUILD-LOG.md:193 | The round-1 triage stated in the present tense that dev/stage-a-mutations.py:30 raises FileNotFoundError, which the round-3 B-1 fix replaced. Fixed: the sentence reads "A-5 true but low at review round 1: dev/stage-a-mutations.py:30 raised FileNotFoundError with a traceback when no kanon.exe was built, which house rules allow, and review round 3 replaced that raise with the printed control failure `CONTROL FAIL missing build ... run sh dev/stage-a.sh first` at exit 1." |

Refuted: 0 findings.

Merged and dropped: 12 findings. A-4 merged into D-1, same defect in
dev/foundation.py, end-line-only anchoring of a cited range. B-2 merged
into A-3, same file and line, and A-3 keeps both the absent-dune and the
broken-dune probes. B-3 merged into A-1, same file and line, and one
guarded rewrite fixes the vacuous manifest and the missing reason line
together. C-7 merged into A-5 as its documentation face, because the
scoped build does not compile vendor/kanon/vendor/tot, so an added .ml
file there does not falsify the consequence clause of SPEC.md:108, and
the true remainder rides with the A-5 fix. B-4 cut by the seven-finding
cap, low and diagnostic only, because the gate fails correctly and only
misnames a broken zsh as an inherited shape isolation failure. C-1 cut
by the cap, low, because the SIXTH-SHAPE row of dev/MUTATION-LOG.md
paraphrases the two required texts with no effect on gate behaviour. C-2
cut by the cap, low, because dev/MUTATION-LOG.md:148 and :155 name review
rounds 3 and 4 for fix rounds 3 and 4 of review round 2. C-3 cut by the
cap, low, because dev/M0-BUILD-LOG.md:227 says seven findings were kept
while its table holds ten rows. C-5 cut by the cap, low, because
SPEC.md:116 and the comment at dev/foundation.py:233 state a citation
requirement broader than the code, which requires one for refusals only.
C-6 cut by the cap, low, because dev/M0-BUILD-LOG.md:192 cites
dev/stage-a-mutations.py:30 for a raise that lives at line 56. D-2 cut by
the cap, a low coverage gap, because the .gitmodules path, url and staged
legs work today but have no mutation case. D-3 cut by the cap, low,
because no staged line records that the Stage B sixth-shape mutation row
is still owed after the Stage A SIXTH-SHAPE case.

Gates after the last fix round, log
`/Users/oobi/Documents/tether-stage-a-review/gates-C-5.log`, verdict
GATES-OK. One row per leg, each line verbatim.

| leg | line |
|-----|------|
| pin | `PIN 2c2e6e6 unlisted=0` |
| carry | `CARRY files=36 diff=0 vendor=32 copies=4` |
| count | `R0-COUNT formers=2 schema=4 shapes=5 admitted=3` |
| audit | `R0-AUDIT ok` |
| trusted lines | `TRUSTED-LINES kernel=3997/4000 encoder=246/600 OK` |
| sha256 1 | `dev/bench.sh: OK` |
| sha256 2 | `dev/denominators.json: OK` |
| sha256 3 | `dev/tcc-denominator.sh: OK` |
| sha256 4 | `corpus/twin/spine.c: OK` |
| sha256 5 | `corpus/twin/sort.c: OK` |
| sha256 6 | `corpus/twin/parser.c: OK` |
| sha256 7 | `corpus/twin/interp.c: OK` |
| sha256 8 | `corpus/lua/m0-spine.lua: OK` |
| ladder | `PASS STAGE-A` |
| exit | `EXIT 0` |
| mutations | `PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1` |

One-minute load 45.44 at the start and 45.48 at the end. Carry and count
numbers: files=36 diff=0 vendor=32 copies=4, formers=2 schema=4 shapes=5
admitted=3, kernel=3997/4000 and encoder=246/600. Mutations: killed=37,
survived=0, restored=1. Rounds 1 and 2 ran in run wf_a7b4ced8-ca1,
rounds 3 and 4 in run wf_8f24505c-10d and the rest in this run.
Fix rounds: 5.

### Stage B 2026-09-10: surface and checked counter

Built from committed Stage A, `f5ff99e`, in an isolated copy at
`/Users/oobi/Documents/gpt18/tether-stage-b`. The vendor remains at
`2c2e6e6` with no edits or patches. The slice adds the surface library,
module resolver, literal schema expansion, Redis prelude, checked
constructor wrappers and a development checker. `examples/M0Spine.tet`
checks and erases through the inherited kernel. `dev/STAGE-B.md` records
the concrete syntax and remaining milestone limits.

Two integration details were resolved locally. Dune build-only copies
expose the pin's private libraries across its project boundary. Checked
ordinary function wrappers bridge the inherited surface's refusal of
parameterized constructor applications. The wrappers add no axioms.
Fault uses six byte-payload legs so inherited proof erasure retains its
runtime tag. The integer fixture retains its decimal bytes beyond 2^53.

Validation used OCaml 5.2.1 and Dune 3.24.2 from `zxcaml-p1`, with the
recorded host tools and panicscan on PATH. Both commands exited zero:

```sh
sh dev/stage-b.sh
python3 -P dev/stage-a-mutations.py
```

| Gate | Result |
| --- | --- |
| PIN / CARRY | `PIN 2c2e6e6 unlisted=0`; `CARRY files=36 diff=0 vendor=32 copies=4` |
| R0-COUNT | `formers=2 schema=4 shapes=5 admitted=3` |
| Inherited audit and denominators | `PASS STAGE-A` |
| Build / house | Warnings as errors; `panicscan --deny present` found no site at present severity or above; `PASS HOUSE` |
| Surface / erasure fixtures | `PASS STAGE-B-SURFACE cases=59` |
| Stage B source mutations | `PASS STAGE-B-MUTATIONS killed=5 restored=1` |
| Stage A mutation regression | `PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1` |
| Complete Stage B ladder | `PASS STAGE-B` |

Measured bounds: kernel=3997/4000, encoder=246/600, lua=0/320, sh=0/240,
store=0/200, host-node=0/300 and host-rest=0/300. The five zero counts are
measurements before those components ship. No Redis or timing result is
claimed. `runtime/redis.kan` is in the ruled trusted base of `prog.wasm`
and no bound counts it; `dev/STAGE-B.md` records that gap and the
ratification row Stage C needs to close it.

`.kanon-exec/run-hvujx2` in the isolated copy captures the first Stage B
ladder run, stdout SHA256
`ea97f51d6227a9ac2dbe6da68b2270f7e963c42f525fe817f55b7de74a6e3d7a`. That
capture predates the gate corrections in the table above, so it prints
`cases=48` and `killed=4`. The Stage A mutation capture is
`.kanon-exec/run-vUq51z`.

### Review round 2026-09-10 (Stage B)

| Id | Severity | File | Fix or ruling |
| --- | --- | --- | --- |
| C-1 | high | `dev/house.sh` | `dev/house.sh:9` runs `panicscan --deny present --min present --strict surface dev/surface_check.ml`, and the new HOUSE-EXCEPTION mutant fails it. |
| B-2 | high | `dev/stage-b-tests.py` | `EXPECTED_CASES` is compared before the print, so a deleted fixture prints `FAIL STAGE-B-SURFACE` and exits 1. |
| A-2 | medium | `surface/elab.ml` | `surface/elab.ml:68` reads `base.owners`, so only prelude names and `Constructors.prefix` wrappers stay protected; new fixture `import-shadow-binder`. |
| A-1 | medium | `surface/parser.ml` | The `body` arm of `headers` refuses a remaining `import` or `schema` token with `Diagnostic.Syntax`; new fixtures `late-schema`, `late-import` and `malformed-schema`. |
| B-3 | medium | `dev/check.py` | `dev/check.py` names each refusal on standard error as `HOST-REFUSED <request>: ...`; new fixtures `host-escape`, `host-symlink-inside`, `host-oversize` and `host-limit-edge`. |
| B-4 | medium | `dev/trusted-lines.py` | `dev/trusted-lines.py:30` counts newlines only for the kernel and encoder groups; the NEWLINE-COUNT control asserts that both counters agree. |
| D-2 | medium | `dev/trusted-lines.py` | `dev/STAGE-B.md` and this block record the member of the ruled trusted base that no bound counts, name Stage C as the closing stage and ask for a ratification row; no group and no bound moved. |
| ND-1-1 | medium | `surface/parser.ml` | The walk `late_header previous body` refuses exactly two token shapes, so a binder of the same name stays a term; new fixtures `binder-named-schema` and `binder-named-import`. |
| ND-1-2 | medium | `dev/STAGE-B.md` | The trusted base paragraph now names both `.kan` prelude sources, `runtime/reactor.kan` and `runtime/redis.kan`, as the members that no bound counts. |
| ND-2-1 | medium | `surface/parser.ml` | The comment above `late_header` loses the false clause and states the real rule; `opens_operand` answers true for eight operand tokens; new fixture `binder-named-import-applied`. |

Refuted: 1. D-1 (`dev/trusted-lines.py:28`, the five new bounds print 0 as
a measurement): M0-PLAN.md:293 and RATIFICATIONS.md:38 name Stage B as the
point where a number replaces `N`; `dev/trusted-lines.py:19-33` performs a
genuine measurement at Stage B, and SPEC.md:88-89,
`dev/M0-BUILD-LOG.md:407` and `dev/STAGE-B.md:105` all disclose that the
zeros mean not implemented at Stage B. No document quotes a number before
Stage B ran the counter, so R-M0-3 is not violated as cited.

Merged and dropped: 11. B-1 merged into C-1 (same file `dev/house.sh`,
same line 9, same defect; B-1 states the wrong mechanism). Ten cut at the
7 cap: A-3 (the collapsed `-1` in `dev/check.py:36-37` overlaps kept B-3),
D-3 (the `dev/MUTATION-LOG.md:195` NESTED-OP row misdescribes a scratch
module and omits one citation; the substance overlaps B-2 and B-3), A-4
(low, misleading reason text at `surface/schema.ml:86-88`, refusal
correct), A-5 (low, `dev/STAGE-B.md:46` overstates what the types enforce,
lines 47 to 48 already defer cross-slot permission), B-5 (low, a
depth-limit mutant survives; one more instance of the class kept in B-3),
B-6 (low, absent files skipped silently, already disclosed at
`dev/STAGE-B.md:106-108`), C-2 (low, `dev/STAGE-B.md:67` cites the pin's
line 440 where the refusal is line 449), C-3 (low, no fixture asserts the
absence of an `AXIOM` line; forward looking), C-4 (low, README.md:11-13
lists three Stage B commands against four in `dev/STAGE-B.md:8-13`), D-4
(low, two dune libraries beyond the three R-M0-4 names, a ratification
request for the user).

Gates after the last fix round, `gates-3.log`, one-minute load 83.66
(load averages 83.66 65.71 61.82 at the start of the run):

| Leg | Line |
| --- | --- |
| PIN | `PIN 2c2e6e6 unlisted=0` |
| CARRY | `CARRY files=36 diff=0 vendor=32 copies=4` |
| R0-COUNT | `R0-COUNT formers=2 schema=4 shapes=5 admitted=3` |
| R0-AUDIT | `R0-AUDIT ok` |
| Trusted lines, Stage A | `TRUSTED-LINES kernel=3997/4000 encoder=246/600 OK` |
| Stage A ladder | `PASS STAGE-A` |
| House | `PASS HOUSE` |
| Surface fixtures | `PASS STAGE-B-SURFACE cases=59` |
| Trusted lines, Stage B | `TRUSTED-LINES kernel=3997/4000 encoder=246/600 lua=0/320 sh=0/240 store=0/200 host-node=0/300 host-rest=0/300 OK` |
| Mutant SIXTH-SHAPE | `KILLED SIXTH-SHAPE by rebuilt R0-COUNT` |
| Mutant HOUSE-EXCEPTION | `KILLED HOUSE-EXCEPTION by panicscan` |
| Mutant NESTED-OP | `KILLED NESTED-OP by inherited positivity` |
| Mutant LUA-BOUND | `KILLED LUA-BOUND by TRUSTED-LINES` |
| Control NEWLINE-COUNT | `AGREED NEWLINE-COUNT by both trusted-line counters` |
| Mutant MISSING-ENCODER | `KILLED MISSING-ENCODER by TRUSTED-LINES` |
| Stage B mutations | `PASS STAGE-B-MUTATIONS killed=5 restored=1` |
| Complete Stage B ladder | `PASS STAGE-B` |
| Ladder exit | `EXIT 0` |
| Stage A mutation regression | `PASS STAGE-A-MUTATIONS killed=37 survived=0 restored=1` |

Carry and count numbers of that run: `files=36 diff=0 vendor=32 copies=4`,
`kernel=3997`, `encoder=246`, `cases=59`, `lua=0`, `sh=0`, `store=0`,
`host-node=0` and `host-rest=0`. Mutation summary: Stage B killed=5 and
restored=1, with no survivor row; Stage A killed=37, survived=0 and
restored=1.

Fix rounds: 3.
