# Do-notation

The first M1 slice adds continuation syntax for Script and Client programs:

```text
def main : Client Reply := do {
  first <- inv Reply (tag b"counter") counter;
  second <- inv Reply (tag b"counter") counter;
  done Reply first
}
```

Each `name <- command;` appends a `fun (name : Reply) => ...`
continuation to the command. The final expression closes the block. This
example runs both commands and returns the first reply. Use `_` when a
reply is unused. The existing explicit type and tag arguments remain on
the command and final expression.

```text
do { r <- action; finalTerm }
```

expands to:

```text
(action) (fun (r : Reply) => (finalTerm))
```

This is constructor continuation sugar. There is no generic monadic bind,
instance search, inferred tag, or additional primitive. Every current
command continuation accepts Reply, while the terminal result type is
checked from the existing explicit arguments. A complete Script value
cannot be used in place of a command awaiting its continuation.

Blocks require a final expression, usually `pure`, `done`, or `fail` with
their ordinary arguments. That expression may have one trailing semicolon.
A bind always needs a semicolon and a following statement. Nested blocks
are expressions and may appear inside parentheses or at the end of a
block. Existing `let name : Type := value in expression` works inside a
block; there is no separate semicolon-terminated let statement.

A reply name is in scope only after its command. Reusing a name shadows
the earlier reply in the following statements. Prelude names retain their
existing binder protection. `do` remains an ordinary identifier unless
followed by `{`. Comments use the existing `--` syntax. Punctuation inside
byte literals and comments is preserved or ignored by the same rules as
before.

The surface lexer recognizes `{`, `}`, `<-`, and `;`, delegates ordinary
spans and byte decoding to the pinned lexer, and expands blocks before
schema expansion and inherited parsing. Malformed blocks report
`SYNTAX DO-SYNTAX line:column ...` using original source positions. A
bare `{`, `}`, `;` or `<-` outside a do block reports
`SYNTAX DO-SYNTAX line:column punctuation outside a do block` where the
pinned lexer reported an unexpected-character error. That wording change
is deliberate, both forms reject the source, and every other legacy
source keeps its pinned diagnostic. The
ordinary checker still enforces command types, slot tags, name scope and
positivity. The existing `SH-FIRST-ORDER` emission refusal still applies
to inline scripts and unsupported Client control.

Run the example and the complete slice gate:

```sh
dune build bin/tether.exe
./tether run examples/DoCounter.tet --entry earlier
./tether exec examples/DoCounter.tet --host node
./tether exec examples/DoCounter.tet --host bash
./tether exec examples/DoCounter.tet --host luajit
sh dev/m1-do.sh
```

The gate includes the M0 ladder. `dev/m1-do.sh` runs every leg even after
a failure, prints `PASS` or `FAIL` for STAGE-F, DO-BUILD, DO-SYNTAX,
DO-TESTS, DO-MUTATIONS and HOUSE, and ends with `PASS M1-DO` or
`FAIL M1-DO` and a non-zero exit. Focused checks are
`dune build dev/do_tests.exe`, `_build/default/dev/do_tests.exe`, and
`python3 -P dev/do-tests.py`. The integration suite starts its own temporary
loopback Redis and REST servers. It compares all emitted files against
explicit continuation programs, then checks stdout and stored effects on
both artifacts. LuaJIT supplies a third reply producer for successful
Clients. Invalid programs must leave no output directory.
The mutation runner changes the Reply binder type, reverses command and
continuation application, drops the continuation tail, and accepts a
second semicolon before the final expression, in disposable source
copies. Every mutant must compile and then fail the syntax tests with the
marker recorded for it in `dev/MUTATION-LOG.md`; the restored expander
must pass.

This slice does not complete M1. Remaining work includes the broader
command surface and application examples, EVALSHA_RO, the counted Lean
exporter, and the M1 performance and traversal gates. The pinned kernel,
preludes, trusted-line bounds and frozen M0 measurements are unchanged.
