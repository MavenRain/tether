# Spike (c): the vendoring form

Date: 2026-09-09.  Kanon pin: 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf.  Rulings applied: R-Q3 and R-M0-2 (RATIFICATIONS.md).  Scratch repository: /Users/oobi/Documents/tether-m0/spikes/pin/, never part of this repository.

## 1 Result

The submodule form works from the main checkout at the pin with no worktree, no clone by hand and no write in /Users/oobi/Documents/kanon.  The flag `-c protocol.file.allow=always` is REQUIRED on this git.  Gate S0-G5 prints:

```
PIN 2c2e6e6 unlisted=0 lib=25 wasm=4 runtime=3
```

## 2 git version

```
$ git --version
git version 2.50.1 (Apple Git-155)
```

## 3 The two submodule add outcomes, verbatim

Without the flag (exit 128):

```
$ git -C /Users/oobi/Documents/tether-m0/spikes/pin submodule add /Users/oobi/Documents/kanon vendor/kanon
Cloning into '/Users/oobi/Documents/tether-m0/spikes/pin/vendor/kanon'...
fatal: transport 'file' not allowed
fatal: clone of '/Users/oobi/Documents/kanon' into submodule path '/Users/oobi/Documents/tether-m0/spikes/pin/vendor/kanon' failed
EXIT-WITHOUT-FLAG rc=128
```

With the flag (exit 0):

```
$ git -C /Users/oobi/Documents/tether-m0/spikes/pin -c protocol.file.allow=always submodule add /Users/oobi/Documents/kanon vendor/kanon
Cloning into '/Users/oobi/Documents/tether-m0/spikes/pin/vendor/kanon'...
done.
EXIT-WITH-FLAG rc=0
```

The flag is a per-command `-c` and is never written into any config file.  The clone lands on branch main of the main checkout, so the next step detaches it at the pin:

```
$ git -C /Users/oobi/Documents/tether-m0/spikes/pin/vendor/kanon checkout --detach 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf
HEAD is now at 2c2e6e6 Change base of dependent elimination along constructor-preserving maps
```

## 4 The three shas

```
SHA-SUBMODULE-HEAD 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf   git -C .../spikes/pin/vendor/kanon rev-parse HEAD
SHA-MAIN-PIN       2c2e6e6831a0b2cf3107fa4aad392606109a2bcf   git -C /Users/oobi/Documents/kanon rev-parse 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf
PIN-FILE           2c2e6e6831a0b2cf3107fa4aad392606109a2bcf   cat .../spikes/pin/PIN, 41 bytes, one trailing LF
```

Also observed, not one of the three: `git -C /Users/oobi/Documents/kanon rev-parse HEAD` printed 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf, and `git -C .../spikes/pin submodule status` printed ` 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf vendor/kanon (heads/main)`.  The .gitmodules written by the add:

```
[submodule "vendor/kanon"]
	path = vendor/kanon
	url = /Users/oobi/Documents/kanon
```

## 5 The printed PIN line and the checks behind it

```
$ zsh /Users/oobi/Documents/tether/dev/spike-pin.sh /Users/oobi/Documents/tether-m0/spikes/pin /Users/oobi/Documents/tether-m0/spikes/pin/PIN
PIN 2c2e6e6 unlisted=0 lib=25 wasm=4 runtime=3
```

dev/spike-pin.sh takes the scratch root and the PIN path.  It checks, in this order: the submodule HEAD equals the PIN content;  `git -C /Users/oobi/Documents/kanon rev-parse --verify PIN^{commit}` equals the PIN content;  every file that `git ls-tree -r --name-only PIN -- lib wasm runtime` lists is present in the checkout and byte identical to `git -C /Users/oobi/Documents/kanon show PIN:PATH` under `cmp -s`;  and no file sits under lib/, wasm/ or runtime/ of the checkout that the pin tree does not list (the unlisted count).  Every read of kanon goes through the commit object, never through the dirty working tree.  The counts are the files the pin lists: 25 under lib/, 4 under wasm/, 3 under runtime/ (reactor.kan, reactor.mjs, run.mjs).  On any mismatch it prints `PIN FAIL <reason>` and exits 1.  Usage errors exit 4.

Probes run on the scratch checkout, each undone after its line (log: /Users/oobi/Documents/tether-m0/spikes/pin-probe.log):

```
stray file lib/stray.txt         PIN FAIL unlisted=1 lib/stray.txt          rc=1
one byte appended to run.mjs     PIN FAIL differs from pin: runtime/run.mjs  rc=1
wasm/emit.ml moved away          PIN FAIL missing in checkout: wasm/emit.ml  rc=1
PIN copy with two chars swapped  PIN FAIL submodule HEAD 2c2e6e68... differs from PIN c22e6e68...  rc=1
```

The last probe is the shape of mutation S0-M3;  the judge reruns it on a copy under /Users/oobi/Documents/tether-m0/mutants/.  After the probes the submodule checkout is clean (`git status --porcelain` prints 0 lines) and the gate line prints again with exit 0.

One trap found while writing the script: zsh ties the lowercase variable `path` to PATH, so a `local path` inside a function empties PATH and every `git` call fails with "command not found".  The loop variable is `rel`.  A second trap: a `fail` called inside a `$(...)` substitution cannot print to the parent's stdout, so the compare loop runs in the main shell.

## 6 Size of the submodule clone

```
$ du -sh /Users/oobi/Documents/tether-m0/spikes/pin/vendor/kanon
 11M	/Users/oobi/Documents/tether-m0/spikes/pin/vendor/kanon
$ du -sh /Users/oobi/Documents/tether-m0/spikes/pin/.git/modules/vendor/kanon
 12M	/Users/oobi/Documents/tether-m0/spikes/pin/.git/modules/vendor/kanon
```

The working tree is 11M and the object store under .git/modules is 12M.  The whole scratch repository reports 12M under `du -sh` because of shared blocks.

## 7 The exact command list Stage A repeats

Stage A runs these inside /Users/oobi/Documents/tether, in this order, and commits nothing.  The submodule add stages .gitmodules and the gitlink itself;  that is the only git add before the closer's `git add -A`.

```
git -C /Users/oobi/Documents/tether -c protocol.file.allow=always submodule add /Users/oobi/Documents/kanon vendor/kanon
git -C /Users/oobi/Documents/tether/vendor/kanon checkout --detach 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf
printf '%s\n' 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf > /Users/oobi/Documents/tether/dev/PIN
git -C /Users/oobi/Documents/tether/vendor/kanon rev-parse HEAD
git -C /Users/oobi/Documents/kanon rev-parse 2c2e6e6831a0b2cf3107fa4aad392606109a2bcf
cat /Users/oobi/Documents/tether/dev/PIN
zsh /Users/oobi/Documents/tether/dev/spike-pin.sh /Users/oobi/Documents/tether /Users/oobi/Documents/tether/dev/PIN
git -C /Users/oobi/Documents/tether add vendor/kanon .gitmodules dev/PIN
```

The three rev-parse and cat lines must print the same 40 hex characters.  The spike-pin.sh line must print `PIN 2c2e6e6 unlisted=0 lib=25 wasm=4 runtime=3`.  Stage A then turns dev/spike-pin.sh into dev/carry-check.sh: same three checks, the root defaults to the repository, the PIN defaults to dev/PIN, and the unlisted set is compared against the names in dev/PATCHES (R-Q3), which is empty at M0.

A fresh clone of tether needs the same flag once: `git -c protocol.file.allow=always submodule update --init vendor/kanon`, then the detach line, since the gitlink records the pin and the URL is a local path.

## 8 What Stage 0 did NOT do

No submodule was added to /Users/oobi/Documents/tether.  No dev/PIN exists there.  The main checkout was not written, not built and no worktree was added;  `git -C /Users/oobi/Documents/kanon status --porcelain` printed 47 lines at the start and at the end of this spike's window, and `git -C /Users/oobi/Documents/kanon worktree list` shows no tether path.
