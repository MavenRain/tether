# tether

tether is a small language for Redis scripts.  A tether program compiles to two artifacts: `prog.wasm` and `prog.sh`.  Both artifacts share the same Lua bodies.

## Status

M0 Stage 0.

## Files

- Source files end in `.tet`.
- A module name is dotted PascalCase.  A module name equals its path under the source root.  The module `Data.Reply` lives in `Data/Reply.tet`.

## Foundation

tether builds on kanon at pin 2c2e6e6.  The submodule `vendor/kanon`, the file `dev/PIN`, the script `dev/carry-check.sh` and the file `SPEC.md` arrive at Stage A.  Stage 0 holds the repository skeleton, the tool record and the spike outputs under `dev/`.

## License

MIT OR Apache-2.0.  See `LICENSE-MIT` and `LICENSE-APACHE`.
