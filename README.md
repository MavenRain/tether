# tether

tether is a small language for Redis scripts.  A tether program compiles to two artifacts: `prog.wasm` and `prog.sh`.  Both artifacts share the same Lua bodies.

## Status

M0 Stage B: the Redis surface and a type-checked counter spine, built on
the pinned foundation. Printers and hosts follow in Stages C to F.

```sh
dune build dev/surface_check.exe
python3 -P dev/check.py --root examples M0Spine.tet
sh dev/stage-b.sh
```

See `dev/STAGE-B.md` for module syntax, schemas, erased constructors,
validation scope and the additional `panicscan` gate dependency.

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
The development checker ships in Stage B. Artifact emission and Redis
execution commands are not shipped yet.

## License

MIT OR Apache-2.0.  See `LICENSE-MIT` and `LICENSE-APACHE`.
