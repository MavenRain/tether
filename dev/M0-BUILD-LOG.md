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
