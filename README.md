# tether

tether is a small language for Redis scripts.  A tether program compiles to two artifacts: `prog.wasm` and `prog.sh`.  Both artifacts share the same Lua bodies.

## Status

M1 now supports typed HSET, HGET, HDEL, HEXISTS, HLEN and HINCRBY on
Hash keys. `./tether exec examples/Hashes.tet --host node` demonstrates
field updates and exact arithmetic beyond 2^53. See `dev/HASHES.md` for
command types, binary reply limits and validation.

M1 now supports typed SET, INCRBY, DECR, DEL and EXISTS alongside INCR
and GET. `./tether exec examples/Strings.tet --host node` demonstrates
exact arithmetic beyond 2^53. See `dev/STRINGS.md` for command types,
examples and validation.

M1 adds `do { reply <- command; finalTerm }` syntax for Script and Client
continuations, plus read-only Redis dispatch. Scripts classified as
`no-writes` use `EVALSHA_RO` and fall back to `EVAL_RO` on NOSCRIPT.
Try `./tether exec examples/ReadOnly.tet --host node` after building the
driver, or select `--entry mixed` to combine reads and writes. See
`dev/DO-NOTATION.md` and `dev/READONLY.md` for syntax and checks.

The Stage F driver emits an executable Client `prog.wasm` and `prog.sh`
with the same canonical Lua bodies. Both run against local Redis hosts
and agree with LuaJIT and the independent store interpreter. The final
M0 timing gate is measured separately from functional correctness; see
`dev/STAGE-F.md` and the latest entry in `dev/M0-BUILD-LOG.md`.

```sh
dune build bin/tether.exe
./tether check examples/M0Spine.tet --passes
./tether emit examples/M0Spine.tet -o .gatework/counter-client
./tether run examples/M0Spine.tet
./tether exec examples/M0Spine.tet --host node
./tether exec examples/M0Spine.tet --host bash
./tether exec examples/M0Spine.tet --host luajit
sh dev/stage-f.sh
```

`exec` starts and stops its own temporary loopback Redis server and REST
twin, then compares the chosen host's stdout with the empty-store
interpreter. The counter commands above print `1`. Emit requires a fresh output directory.

```sh
dune build dev/surface_check.exe
python3 -P dev/check.py --root examples M0Spine.tet
sh dev/stage-b.sh
dune build dev/lua_emit.exe dev/sha1_probe.exe
python3 -P dev/emit-lua.py --root examples M0Spine.tet -o .gatework/counter
sh dev/stage-c.sh
dune build dev/sh_emit.exe
python3 -P dev/emit-sh.py --root examples M0Spine.tet -o .gatework/bash-counter
sh dev/stage-d.sh
sh dev/stage-e.sh
```

See `dev/STAGE-B.md` for module syntax, schemas, erased constructors,
validation scope and the additional `panicscan` gate dependency.
See `dev/STAGE-C.md` for Lua emission, artifact inspection and validation.
See `dev/STAGE-D.md` for Bash emission, reply formatting and current limits.
See `dev/STAGE-E.md` for local hosts, the store and integration validation.
See `dev/STAGE-F.md` for the driver, compiled Client and measurement scope.

## Files

- Source files end in `.tet`.
- A module name is dotted PascalCase.  A module name equals its path under the source root.  The module `Data.Reply` lives in `Data/Reply.tet`.

## Foundation

tether builds on kanon at pin 2c2e6e6, carried as `vendor/kanon` with zero
patches. See `SPEC.md` and `dev/PIN`. Stage 0's tool record and frozen spike
outputs remain under `dev/`.

Initialize the submodule, then run the foundation gates. The gates need Git,
Python 3.11 or newer for the `-P` flag, zsh, ripgrep, shasum, awk, wc, OCaml
5.2.1, Dune 3.24.2 and Zarith 1.14 on PATH:

```sh
git -c protocol.file.allow=always submodule update --init vendor/kanon
sh dev/stage-a.sh
python3 -P dev/stage-a-mutations.py
```

Run the three commands in this order. `sh dev/stage-a.sh` builds
`vendor/kanon/bin/kanon.exe`, and the mutation battery copies that
executable into every temporary tree. Without the build the battery stops
with a control failure.

The submodule URL is the ruled local `/Users/oobi/Documents/kanon` path.
After initialization, builds and gates use only `vendor/kanon`.
The development emitter writes `script.lua`, `body.wasm` and `script.json`.
The Bash emitter writes `prog.sh`, the Client schedule, keys and one
Lua/Wasm carrier pair per script. The Node integration runner executes
that schedule using the Wasm carriers and a loopback Redis server.
The `tether` command emits the full Client Wasm and Bash pair. The earlier
development emitters remain available for inspecting per-script carriers.

## License

MIT OR Apache-2.0.  See `LICENSE-MIT` and `LICENSE-APACHE`.
