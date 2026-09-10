# Stage B surface

The entry point is `Elab.check` in the `tether_surface` Dune library. It
takes a Result-returning file reader, a source-relative entry path, both
prelude texts and an explicit kernel budget. The development host provides
filesystem IO; it confines imports to the selected source root, follows
symlinks only within that root, and limits each source to 1 MiB.

```sh
dune build dev/surface_check.exe
python3 -P dev/check.py --root examples M0Spine.tet
python3 -P dev/check.py --root examples M0Spine.tet --erased
sh dev/stage-b.sh
```

Use the toolchain in `dev/TOOLCHAIN.md`. The Stage B house gate also needs
the installed `panicscan` CLI. The checker has a default budget of one
million kernel polls, shared by prelude checking, wrapper checking, user
definitions and optional erasure. `--fuel 0` exercises exhaustion. The
full `tether` command and artifact emission remain later-stage work.

## Modules and schemas

Every source starts with `module Name`. Names are dotted PascalCase and
must match their path: `Data.Keys` lives at `Data/Keys.tet`. The spine is
`examples/M0Spine.tet`, using `examples` as its source root. This replaces
the plan's illustrative lowercase filename to obey the module-path rule.
Imports and schemas precede inherited declarations. An `import` or
`schema` header written after the first declaration, and a `schema`
header whose shape does not match the form below, both print `SYNTAX`;
neither becomes term tokens. Two token shapes open a header: `import`
followed by a name that starts with a capital letter, and `schema`
followed by a name and a colon. Outside those two shapes both words stay
ordinary identifiers, so a local binder can carry either name. A use of
that binder stands where an operand is required, after `(`, `:`, `:=`,
`->`, `=>`, `*`, `,` or `|`, and the checker reads it as a term. After a
name the checker reads the two shapes as a late header and prints
`SYNTAX`, because the grammar carries no terminator that tells an
argument apart from the next declaration. A schema header reads:

```text
module Data.Keys
schema hits : String -> Key (Str Int64) tag b"counter"
```

An importing module writes `import Data.Keys` and uses `hits b"visits"`.
The expansion constructs `Key (Str Int64) (tag b"counter")` with physical
bytes `{counter}:hits:visits`. Both tag and index must be nonempty and
contain no braces, including escaped braces. `String` in a schema header
describes its byte-string index domain. M0 indexes are literal bytes; a
dynamic index produces `SLOT-STATIC` requesting a literal annotation.

Schema types include `Str Int64`, `Str Binary`, `Hash`, `List`, `Set`,
`ZSet` and `Stream`. Only INCR and GET have command constructors here.
Direct schema misuse prints `WRONGTYPE`; all applications, including keys
passed through variables, still go through kernel type checking. The
Script tag index prevents a continuation from switching slots. Cross-slot
permission and its emitted flag belong to subsequent surface/printer work;
Stage B implements the single-slot counter contract.

Imports open the transitive dependency exports. Each module checks against
its own imports, so one sibling cannot read another sibling's definitions
without importing it. A diamond dependency is read and checked once.
Distinct modules exporting the same name fail with `DUPLICATE`, even if
their definitions have identical bodies. Cycles and mismatched module
headers fail before checking. There is no qualified term-name syntax yet.

## Kernel and erasure

`runtime/redis.kan` is checked after the byte-identical carried reactor.
It declares indexed Key, mutual Reply/Replies, and parameterized Script
and Client families. Script has an erased result-type parameter and an
erased Tag index. Its INCR/GET continuations are strictly positive. Fault
is a six-leg collection sum with byte payloads for diagnostic messages;
the six named constants have empty payloads. Byte payloads keep the fault
discriminant at runtime under the inherited proof-erasure rules.

The pin's `surface/elab.ml:440` refuses applications of parameterized
constructors even when a surrounding annotation provides the type.
`surface/constructors.ml` builds ordinary kernel function definitions for
the prelude's constructors. Each wrapper has the family's erased
parameters followed by its constructor telescope. `Check.check_decls`
checks every wrapper before it joins the environment. The source uses
explicit erased parameters, for example `pure Reply (tag b"counter") x`.
`surface/rewrite.ml` rewrites expression references to these wrappers;
pattern constructor names stay unchanged. The spine's erased INCR wrapper
has only a key and a continuation, with no Tag or result-type argument.

`int64 b"9007199254740993"` constructs a Signed64 refinement with the exact
decimal bytes. The surface checks canonical spelling and signed 64-bit
bounds using digit comparisons, without numeric conversion. The raw Key
and Signed64 constructors are reserved. Local binders cannot shadow
prelude names or generated wrapper names and capture schema expansions.
Only those two sets are reserved. A name exported by an imported module
stays available as a local binder name, because no generated term refers
to it.

`foundation/kernel/dune` and `foundation/surface/dune` import the pin's
private libraries into Tether's Dune project using build-only `copy_files`
rules. Copies exist only under `_build`. No vendored file changes, no
kernel patch is introduced, and CARRY still checks the original sources.

## Validation scope

`stage-b.sh` runs Stage A, builds the surface with warnings as errors,
runs the house scan and checker fixtures, measures all seven trusted-line
bounds, then runs the source mutations. The fixtures cover erasure, exact
integer bytes and bounds, invalid keys, slot/type mismatches, constructor
and binder protection, generic Script construction, all Reply and Fault
variants, import diamonds, sibling isolation, collisions and cycles.
They also cover late and malformed headers, a local binder named
`schema` and one named `import`, an imported export used as a
local binder, a symlink that leaves the source root against one that
stays inside it, and a source of 1048577 bytes against one of 1048576.
The host names each refusal on standard error with `HOST-ESCAPE`,
`HOST-OVERSIZE` or the operating system reason, so a size assertion
cannot be satisfied by a missing file. `stage-b-tests.py` compares its
case count against the recorded number and fails when they differ.

The mutations rebuild the declared-shape count after adding `SSixth`,
add an exception site to a surface source and require the house gate to
deny it, check a literal nested `Op (Script A)` against the inherited
positivity checker, exceed the Lua bound, and remove the encoder source.
Each has a positive control and a restored control in a disposable tree.
One further control strips the final newline from a trusted kernel source
and requires the two trusted-line counters to print one kernel number.

The seven bounds currently measure kernel 3997/4000, encoder 246/600,
lua 0/320, sh 0/240, store 0/200, host-node 0/300 and host-rest 0/300.
Zero measures files not implemented at Stage B and does not claim those
components ship. `trusted-lines.py` lists the counted files explicitly;
later stages must extend that inventory for additional implementation
files and require their presence. Surface code is checked by the inherited
kernel and is outside these seven bounds.

The kernel and encoder groups count newlines only, which is what the
carried `dev/inherited/trusted-lines.sh` does with `wc -l`. Both counters
run in one ladder, so a trusted source without a final newline must not
make them print two kernel numbers. The remaining five groups also count
a last line that has no final newline.

The ruled trusted base of `prog.wasm` is lib, wasm, `runtime/reactor.kan`,
`runtime/redis.kan` and `runtime/redis-host.mjs`. The two `.kan` prelude
sources, `runtime/reactor.kan` and `runtime/redis.kan`, are the members
of that base that no bound counts, so `runtime/redis.kan` can grow
without a gate. No ruled bound moves at
Stage B and no group changes here. Stage C closes this, and it needs a
new ratification row for an eighth counted group that holds the prelude
sources. The Tether owner must request that row.

End-to-end Redis and timing claims remain outside Stage B.
