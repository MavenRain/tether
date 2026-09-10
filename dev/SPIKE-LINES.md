# Spike (d): the trusted-line headroom

Date: 2026-09-09.  Kanon pin: 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf.  Owner: Stage 0 spike (d).  This spike reads and writes no OCaml.  Every number below was printed by `wc -l` or by dev/trusted-lines.sh on an export of the pinned commit.

## 1 The export

The commit was exported with `git archive`, never with a worktree, a clone or a read of the dirty main checkout:

```
mkdir -p /Users/oobi/Documents/tether-m0/spikes/lines/kanon-2c2e6e6
git -C /Users/oobi/Documents/kanon archive 2c2e6e6 | tar -x -C /Users/oobi/Documents/tether-m0/spikes/lines/kanon-2c2e6e6
```

The export holds bin, dev, dune, dune-project, examples, lib, LICENSE-APACHE, LICENSE-MIT, meta, PIN, REACTOR.md, README.md, runtime, SPEC.md, surface, test, vendor and wasm.  It is scratch and never enters the repository.

## 2 The trusted-lines run

Command: `zsh /Users/oobi/Documents/tether-m0/spikes/lines/kanon-2c2e6e6/dev/trusted-lines.sh`.  No root argument was passed.  The script derives its root from its own path (`root=${1:-${0:A:h}/..}`, its SA-D7 comment), so the export measured itself.  The script is 80 lines, as section 2 of the brief states.

Printed line, exit 0:

```
TRUSTED-LINES kernel=3997/4000 encoder=246/600 OK
```

The kernel count is the `wc -l` total over twelve files under lib/: shape.ml 60, term.ml 133, rules.ml 1481, check.ml 538, value.ml 137, eval.ml 297, conv.ml 396, totality.ml 146, positivity.ml 118, global.ml 130, order.ml 510 and bignum.ml 51.  The sum is 3997.  The encoder count is `wc -l` of wasm/gc_encode.ml, 246.  The bounds inside the script are kernel 4000 and encoder 600.

## 3 The kernel headroom

4000 minus 3997 is 3.  Three lines is less than the smallest new leg, the store at 120 to 180 lines (dossier-kanon:171), by a factor of 40 or more.  So the store lives outside lib/ as the dune library tether_store in store/ (R-M0-4), and the two printers live outside lib/ in print/ as tether_print.  No file that Stage 0 to Stage F writes lands in a counted kernel file, and no counted kernel file is edited, because a fourth line in any of the twelve files prints `TRUSTED-LINES kernel=4001/4000 ... FAIL` and exits 1.  The encoder headroom is 600 minus 246, 354 lines, and M0 to M2 need zero patches to it (R-Q3), so it also stays at 246.

## 4 The five projected counts

Each projection is a sum of parts, each part sized from the exported file the leg most resembles and from the dossier's decomposition (dossier-kanon:171).  The bounds are the ruled five of R-M0-3.  These are projections;  the TRUSTED-LINES leg prints each of the five as `N` until Stage B measures it (plan correction 3), and no document quotes a measured number before that.

| leg | file | basis in the export | basis `wc -l` | projected | bound | headroom |
| --- | --- | --- | --- | --- | --- | --- |
| lua | print/lua.ml | lib/eterm.ml | 117 | 250 | 320 | 70 |
| sh | print/sh.ml | lib/pp.ml | 102 | 200 | 240 | 40 |
| store | store/ (all .ml files) | lib/eval.ml | 297 | 160 | 200 | 40 |
| host-node | runtime/redis-host.mjs | runtime/reactor.mjs | 275 | 170 | 300 | 130 |
| host-rest | runtime/rest-twin.mjs plus runtime/rest-decode.mjs | runtime/reactor.mjs and runtime/run.mjs | 275 and 28 | 160 plus 50, 210 | 300 | 90 |

### 4.1 lua, 250 of 320

Basis lib/eterm.ml, 117 lines: the erased alphabet with its `print_ktm` printer over the 14 ktm arms at eterm.ml:86-101, 16 lines, and `Erase.print` at erase.ml:1474-1483, 10 lines, which together cover the arms in under 40 lines.  Parts: 40 for the 14 arms plus KFun, 80 for the name table and `local` scoping, 60 for the `redis.call` rule per Postulate and the `#!lua flags=` derivation, 40 for the pcall Err capture, 30 for the module header, the signature and the buffer helpers.  Sum 250.  The dossier range is 250 to 320.  Headroom 320 minus 250 is 70, so the whole 30-line top of the dossier range still fits with 40 to spare.

### 4.2 sh, 200 of 240

Basis lib/pp.ml, 102 lines: a text printer over terms, the same shape as a Bash printer that writes one first-order body.  Parts: 40 for the 14 arms of which 6 are refusal arms that print the named refusal (KClos, KTail, KFun and the three the dossier lists beside them), 20 for the prog.sh header carried as a string, 40 for quoting and base64, 50 for the jq envelope dispatch and the `case` with its `*) exit 4` arm (R-Q6), 20 for the quoted-heredoc body assignment with no trailing newline (R-M0-6), 30 for the module header, the signature and the buffer helpers.  Sum 200.  The dossier range is 180 to 240.  Headroom 240 minus 200 is 40.

### 4.3 store, 160 of 200

Basis lib/eval.ml, 297 lines: call-by-value evaluation over the 13 term constructors with `eval`, `whnf` and `quote`.  The store folds an erased Script value by its constructors against a string map, which is one fold and not three, over 6 command constructors plus `pure`, so about half the loop shape of eval.ml.  Parts: 50 for the six commands over `Map.Make (String)`, 70 for the interpreter fold over the erased Script, 30 for the Reply type, the bulk-string integer path (R-X2) and the error rows, 10 for the module header.  Sum 160.  The dossier range is 120 to 180.  Headroom 200 minus 160 is 40.  The count covers every .ml file under store/, so a split into two files does not change the leg.

### 4.4 host-node, 170 of 300

Basis runtime/reactor.mjs, 275 lines: the reactor loop with `perform` over request codes 0 to 9 at reactor.mjs:173-207 and the 60-line run loop at reactor.mjs:249-269.  The dossier's cheaper seam is a copy of the loop into redis-host.mjs with one new `case 10`, since `perform` is not a parameter.  Parts: 60 for the copied loop, 20 for the new case, 15 for the RESP2 command encoder, 50 for the RESP2 reply decoder over the five reply types, 25 for the `net` connection, the usage line and the exit codes of run.mjs.  Sum 170.  The dossier figure is about 100, which counts the case and the client and not the copied loop.  Headroom 300 minus 170 is 130.

### 4.5 host-rest, 210 of 300

Basis runtime/reactor.mjs, 275 lines, for the twin, and runtime/run.mjs, 28 lines, for the exit-code and usage shape of the decoder.  runtime/rest-twin.mjs parts: 40 for the `http` server and the request read, 50 for the dispatch of the six commands over one in-memory map, 40 for SCRIPT LOAD, EVALSHA, EVAL and the NOSCRIPT reply (R-Q5), 20 for the REST envelope, 10 for the one log line per request that LOAD-ONCE counts (R-M0-5).  Sum 160.  runtime/rest-decode.mjs parts: 40 for the `result` and `error` envelope over integer, bulk string, nil and array, 10 for the header and the export.  Sum 50.  The decoder is its own file so that DECODERS-SPLIT can prove that the two node decoders are separate (R-Q4).  Total 210.  The dossier figure is about 120 for the twin alone.  Headroom 300 minus 210 is 90.

## 5 Summary

Five projected counts: 250, 200, 160, 170 and 210 against 320, 240, 200, 300 and 300.  Five headrooms: 70, 40, 40, 130 and 90.  Every projection is under its bound.  The kernel stays at 3997 of 4000 with 3 lines of headroom and the encoder at 246 of 600, and no new leg touches either.
