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
