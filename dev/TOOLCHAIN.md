# tether toolchain record, Stage 0a

Date: 2026-09-09.  Host: macOS on arm64.  Every version below was read by the command in the last column on this date, through /Users/oobi/Documents/tether-m0/spikes/versions.sh.

Stage 0a has no install step (R-Q7).  Every tool that M0 needs is present.  No agent installs software.

jq 1.6 is pinned and counted in the trusted base (R-X2).  wasm-opt, the Redis server and Upstash sit outside every trusted count (M0-PLAN.md section 11).

| Tool | Status | Version | Command |
| --- | --- | --- | --- |
| redis-server | present, /opt/homebrew/bin | Redis server v=8.10.1 sha=00000000:1 malloc=libc bits=64 build=81870544b30d700a | `redis-server --version` |
| redis-cli | present, /opt/homebrew/bin | redis-cli 8.10.1 | `redis-cli --version` |
| wasm-tools | present, /opt/homebrew/bin | wasm-tools 1.258.0 | `wasm-tools --version` |
| luajit | present, /opt/homebrew/bin | LuaJIT 2.1.1787165859 | `luajit -v` |
| tcc | present, /Users/oobi/.local/bin | tcc version 0.9.28rc 2026-09-04 mob@0fb54300 (AArch64 Darwin) | `tcc -v` |
| wasmtime | present, /opt/homebrew/bin | wasmtime 48.0.1 (7bac2c277 2026-08-24) | `wasmtime --version` |
| node | present, /opt/homebrew/bin | v23.10.0 | `node --version` |
| wasm-opt | present, /opt/homebrew/bin, outside every trusted count | wasm-opt version 130 | `wasm-opt --version` |
| bash | present, /bin/bash | GNU bash, version 3.2.57(1)-release (arm64-apple-darwin25) | `/bin/bash --version` |
| curl | present, /usr/bin | curl 8.7.1 (x86_64-apple-darwin25.0) libcurl/8.7.1 | `curl --version` |
| jq | present, /opt/homebrew/bin, pinned and counted (R-X2) | jq-1.6 | `jq --version` |
| shasum | present, /usr/bin | 6.02 | `shasum --version` |
| python3 | present, /opt/homebrew/bin, the timer of dev/bench.sh | Python 3.14.7 | `/opt/homebrew/bin/python3 --version` |
| ocaml | present, /Users/oobi/.opam/zxcaml-p1/bin, unused at Stage 0 | The OCaml toplevel, version 5.2.1 | `ocaml -version` |
| dune | present, /Users/oobi/.opam/zxcaml-p1/bin, unused at Stage 0 | 3.24.2 | `dune --version` |
| dunecho | present, /Users/oobi/.local/bin, unused at Stage 0 | 0.1.0 | `dunecho --version` |
| git | present, /usr/bin | git version 2.50.1 (Apple Git-155) | `git --version` |
| lua (PUC) | absent, not needed at M0 | ABSENT | `command -v lua` |
| hyperfine | absent, not needed at M0 | ABSENT | `command -v hyperfine` |
| webdis | absent, not needed at M0 | ABSENT | `command -v webdis` |
| upstash CLI | absent, not needed at M0 | ABSENT | `command -v upstash` |

The Redis server and Upstash are outside every trusted count.  The Lua twin runs as `luajit -joff` (R-Q7).  Nothing builds at Stage 0, so ocaml, dune and dunecho are recorded and not used.
