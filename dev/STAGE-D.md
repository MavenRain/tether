# Stage D Bash emission

The development emitter checks a closed `Client Reply` entry and writes
an executable Bash 3.2 script. It follows straight-line invocations of
named, closed `Script Reply` definitions. Static helpers, lets and captured
replies are supported. A continuation can return an earlier reply, invoke
another script, or end in an explicit Client fault.

```sh
dune build dev/sh_emit.exe
python3 -P dev/emit-sh.py --root examples M0Spine.tet -o .gatework/bash-counter
sh dev/stage-d.sh
```

The output directory must be new. It contains `prog.sh`, `scripts.json`
and a numbered `body-N.lua`/`body-N.wasm` pair per distinct script entry.
The Wasm files are the Stage C import-free byte carriers. They do not yet
execute Client requests. Stage E supplies the real hosts and store; Stage
F supplies the full `tether` command and the complete `prog.wasm` artifact.

Run `prog.sh` with `TETHER_URL` and `TETHER_TOKEN` exported for a local REST
twin. The artifact needs `/bin/bash`, curl and exactly jq 1.6. It checks
the jq version before making a request. The Stage D gate uses a curl stub
with real jq and opens no socket. It does not claim the later E2E-3WAY or
real-host LOAD-ONCE gates.

Each Lua body is assigned through a quoted heredoc using Bash's `read`
builtin. Removing the one framing newline preserves the canonical bytes.
The gate runs those assignments and compares their values with the Lua
files and the bytes extracted from each Wasm module. It also compares a
captured SCRIPT LOAD request with the corresponding Wasm body.

The generated program loads each distinct script entry on first use and
checks the returned SHA-1. Later invocations use EVALSHA, or EVALSHA_RO
for no-writes bodies since the M1 read-only slice. Only an error envelope
with the exact NOSCRIPT code triggers EVAL or EVAL_RO respectively, once,
with the same body and keys. Repeated invocations keep their load state in the current
Bash process. Every request is a JSON array constructed by `jq -n --args`.
Keys use quoted octal byte literals. Curl ignores its user configuration,
uses a 30-second timeout, and maps HTTP and network failure to exit 4.

The complete JSON envelope stays in a variable until its variant is
checked. A response must contain exactly one `result` or string `error`
field. Each shell `case` has a default arm that exits 4. Strings print
directly through jq, preserving embedded NUL and trailing newlines in
the payload. Null prints an empty line. Safe integer numbers print as
decimal text. Arrays print compact JSON, including nested arrays. This
avoids flattening nested Reply arrays into an ambiguous TSV string.
Every successful result adds one output newline.

Integers outside the safe JSON-number range must arrive as strings.
Unsafe numbers, fractional numbers, booleans and object payloads are
refused, including inside arrays. Invalid envelopes, malformed JSON,
server errors and explicit Client faults exit 4. Both the script load
and the invocation report the server error text on stderr. Payload bytes are never
evaluated as shell code, and the artifact does not print its token.

This slice refuses higher-order applications, partial application,
dynamic Client branching and inline or parameterized scripts with
`SH-FIRST-ORDER`. Data-dependent control belongs inside the Lua script.
The terminal `done` currently returns an invocation reply; construction
of a new Reply in the Client tier is also refused. NUL and non-ASCII keys
receive `SH-KEY-TEXT`, since jq's text arguments cannot preserve arbitrary
Redis key bytes. Binary values can still pass through JSON strings.
All front-end and static-control walks share the explicit kernel budget.
At fuel 0 the checker exhausts that budget before the static walk starts,
so one gate case pins the checker's `CHECK budget` refusal. The front end
and erasure of `M0Spine.tet` spend 89113 polls with the M1 bulk List pop
prelude and the static walk spends 12, so fuel 89113 through 89124 reaches
the printer's own guard. A second gate case runs at fuel 89119 and pins
`SH-BUDGET`.
Resource exhaustion in other printer work remains residual.

`print/sh.ml`, including its generated header, counts within the existing
240-line bound. Its presence is now mandatory in TRUSTED-LINES. The gate
includes syntax, byte agreement, request order, exact reply text,
refusals and five mutation controls. Both missing-default mutants remain
valid Bash syntax and are caught by executable reply comparisons. The
payload dispatch's default arm is unreachable behind the emitted
`envelope`, so its control substitutes an `envelope` that sets an unknown
kind. Source
mutations run in temporary copies and restore their positive controls.
