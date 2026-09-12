# Stage E store and local hosts

Stage E runs the counter through LuaJIT, the Node Redis host, the generated
Bash Client and an independent OCaml store interpreter. The gate starts a
temporary Redis server and REST twin on loopback, resets the store before
each execution, compares exact stdout bytes and stops both processes on
success or failure.

```sh
sh dev/stage-e.sh
```

This includes the Stage A through D ladders. In addition to their tools,
the host tests use Node with WasmGC and `String.isWellFormed` support
(Node 22 or newer), Redis server and CLI, and LuaJIT. Redis 8.10.1 is the
recorded local server. No external endpoint or account is required.

The development Bash emitter now also writes `client.json`, containing
the checked straight-line invocation schedule and final reply index.
`scripts.json` adds each script's keys. `dev/run-node.mjs` reads the
schedule, extracts each body and SHA-1 from its Wasm carrier, verifies the
Lua bytes and invokes `runtime/redis-host.mjs`. This exercises the real
Node transport. The complete generated `prog.wasm` Client and the `tether`
driver remain Stage F work, after the user commits Stage E.

```sh
dune build dev/sh_emit.exe
python3 -P dev/emit-sh.py --root examples M0Spine.tet -o .gatework/hosts
TETHER_REDIS_PORT=6379 node dev/run-node.mjs .gatework/hosts
```

The Node host also exports `runReactor(path, port, output)`. Request code
10 takes `[sha1, ...keys]` and a Lua body. It resumes the compiled program
with status 0 and a JSON result envelope, or status 1 and an error
envelope. Code 6 writes bytes and code 0 returns the exit code. A compiled
probe exercises two invocations and the error status independently of
the development schedule.

Each Node Client and generated Bash process loads a script on first use,
verifies the returned SHA-1, invokes through EVALSHA and retries only an
exact NOSCRIPT error with EVAL. Since the M1 read-only slice, no-writes
bodies use EVALSHA_RO and EVAL_RO instead, as described in `dev/READONLY.md`.
The same body and keys reach the fallback.
A second error terminates the invocation. The real Node test flushes the
Redis script cache between requests. LOAD-ONCE checks the REST twin's
request log: two warm-up requests (LOAD and the first EVALSHA), then one
request for the second invocation in `ShCases.twice`.

The REST twin binds only to `127.0.0.1`. It requires a bearer token and
accepts POST `/` with a JSON array of strings containing SCRIPT LOAD,
EVALSHA, EVAL, EVALSHA_RO or EVAL_RO. It forwards to a loopback Redis port. Start it with
`TETHER_REDIS_PORT` and `TETHER_TOKEN`; `TETHER_REST_PORT` defaults to an
automatically assigned port. It prints `REST-UP port=...`. Optional
`TETHER_REST_LOG` records one JSON line per completed HTTP request, with
the method, status and allowlisted command names, excluding tokens, bodies
and keys. A refused command records the fixed name `other`, so request text
never reaches the log.
Set `TETHER_URL` to that loopback URL when running `prog.sh`.

The Node and REST paths own separate RESP2 parsers. Both handle fragmented
bulk strings and nested arrays, preserve null and error variants, reject
malformed frames and refuse unsafe numeric replies. Bulk strings retain
exact decimal integers past 2^53. These text hosts reject invalid UTF-8
instead of replacing bytes; UTF-8 NUL, BOM and trailing newlines survive.
Nested Redis errors are refused at the text boundary. Requests and replies
are limited to 8 MiB, nesting to 64 levels and Redis requests to five
seconds. Resource exhaustion inside synchronous Wasm remains residual.

`store/store.ml` represents all six Redis data kinds. M0 operations are
GET and INCR on strings; the other kinds produce WRONGTYPE. Signed
integers must be canonical decimal text in the Int64 range, and overflow
leaves the persistent store unchanged. `store/interp.ml` evaluates erased
Client and Script terms, including closures, captured replies and case
analysis, under an explicit budget. Its result variants preserve the
Reply constructors, and the end-to-end comparison pins the constructor of
every case. The development runner checks `Client Reply` first.

Ten integration cases cover the counter, repeated calls, captured replies,
literal large integers, both Int64 endpoints, missing keys and trailing
newlines. Store unit checks cover invalid numeric strings, wrong data
types, persistence and fuel. Host tests cover malformed or fragmented
RESP, authentication, request framing, load errors, exact NOSCRIPT
matching, truncation, deadlines and the refused-command request log. The independent Lua test store
implements decimal increment without converting the value to a float.

Stage E requires every store and host source in TRUSTED-LINES and rejects
unlisted implementation files. The inherited limits are unchanged.
Mutation controls replace INCR with DECR while updating the shell body's
SHA-1, re-export one decoder from the other, copy the Node decode body into
the REST file, delete each required source, exceed each new bound and add
uncounted store or host sources as `.ml`, `.mli`, `.mjs` and `.js`. Positive controls run
before and after mutation.
