#!/usr/bin/env python3
"""Exercise the real checker and its file host using isolated fixture roots."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPINE = (ROOT / "examples/M0Spine.tet").read_text()
CASE_COUNT = 0


EXPECTED_CASES = 59


def check(name, files, expected=None, entry="M0Spine.tet", erased=False, contains=(), fuel=1000000,
          links=()):
    global CASE_COUNT
    with tempfile.TemporaryDirectory(prefix="tether-surface-") as directory:
        root = Path(directory)
        for path, source in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source)
        for path, destination in links:
            link = root / path
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(destination if Path(destination).is_absolute() else root / destination)
        command = [sys.executable, "-P", str(ROOT / "dev/check.py"), "--root", str(root), entry, "--fuel", str(fuel)]
        if erased:
            command.append("--erased")
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    passed = (result.returncode == 0 and "PASS SURFACE" in output) if expected is None else (
        result.returncode == 1 and expected in output)
    if not passed or any(text not in output for text in contains):
        sys.exit(f"FAIL SURFACE-TEST {name} exit={result.returncode}\n{output}")
    print(f"PASS SURFACE-TEST {name}", flush=True)
    CASE_COUNT += 1


def single(name, source, expected=None, **kwargs):
    check(name, {"M0Spine.tet": source}, expected, **kwargs)


def byte_ir(text):
    tail = "KTag mu<Bytes> 0 []"
    for byte in reversed(text.encode()):
        tail = f"KTag mu<Bytes> 1 [KLit {byte}; {tail}]"
    return tail


single("spine", SPINE)
single("erasure", SPINE, erased=True,
       contains=(byte_ir("9007199254740993"), byte_ir("{counter}:hits:visits"), "fun main",
                 "fun tetherCtor_incr (union mu<Key>, func fn<1>)",
                 "fun Noscript", "fun Discarded"))
for value in ("0", "-1", "9007199254740993", "9223372036854775807", "-9223372036854775808"):
    single("int64-" + value, f'module M0Spine\ndef value : Signed64 := int64 b"{value}"')
for value in ("", "+1", "01", "-0", "-01", "1_0", "0xff", "9223372036854775808", "-9223372036854775809"):
    single("bad-int64-" + value, f'module M0Spine\ndef value : Signed64 := int64 b"{value}"', "INT64")
for value in ("", "a{b", "a}b"):
    single("bad-index-" + value, SPINE.replace('hits b"visits"', f'hits b"{value}"'), "SLOT-STATIC")
    single("bad-tag-" + value, SPINE.replace('tag b"counter"', f'tag b"{value}"'), "SLOT-STATIC")
single("dynamic-index", SPINE.replace('hits b"visits"', 'hits (bytesCons 49 bytesNil)'), "SLOT-STATIC")
single("wrongtype", SPINE.replace('Key (Str Int64) tag', 'Key List tag'), "WRONGTYPE")
single("wrong-encoding", SPINE.replace('Key (Str Int64) tag', 'Key (Str Binary) tag'), "WRONGTYPE")
single("wrongtype-through-variable", '''module M0Spine
schema lists : String -> Key List tag b"counter"
def listKey : Key List (tag b"counter") := lists b"visits"
def bad : Script Reply (tag b"counter") :=
  incr Reply (tag b"counter") listKey (fun (r : Reply) => pure Reply (tag b"counter") r)
''', "CHECK mismatch")
single("fuel", SPINE, "CHECK budget", fuel=0)
single("wrong-slot", SPINE.replace('tag b"counter"\n', 'tag b"other"\n'), "CHECK mismatch")
single("key-constructor", SPINE + '\ndef forged := keyBytes', "RESERVED keyBytes")
single("integer-constructor", SPINE + '\ndef forged := signed64Bytes', "RESERVED signed64Bytes")
single("prelude-shadow", SPINE + '\ndef tag : Nat := 0', "DUPLICATE tag")
single("binder-capture", SPINE + '\ndef bad : Nat -> Nat := fun (tag : Nat) => tag', "RESERVED binder tag")
single("duplicate-schema", SPINE.replace('def counter', 'schema hits : String -> Key List tag b"counter"\ndef counter'), "DUPLICATE hits")
single("duplicate-def", SPINE + '\ndef main : Nat := 0', "DUPLICATE main")
single("path-mismatch", SPINE.replace('module M0Spine', 'module Wrong'), "MODULE-PATH")
single("lowercase-module", SPINE.replace('module M0Spine', 'module wrong'), "MODULE-PATH")
single("missing-module", SPINE.replace('module M0Spine', ''), "SYNTAX")
single("missing-import", 'module M0Spine\nimport Absent', "READ Absent.tet")
single("nested-op", '''module M0Spine
mu Op (0 A : Type 0) : Type 0 := | wrap : A -> Op A
mu Bad (0 A : Type 0) : Type 0 := | nested : Op (Bad A) -> Bad A
''', "not strictly positive")
single("negative-continuation", '''module M0Spine
mu Bad : Type 0 := | negative : (Bad -> Reply) -> Bad
''', "not strictly positive")
single("reply-array", '''module M0Spine
def allReplies : Reply := array (repliesCons nil (repliesCons
  (int (int64 b"9007199254740993")) (repliesCons (bulk b"bulk")
  (repliesCons (status b"OK") (repliesCons (err b"ERR") repliesNil)))))
''')
single("faults", '''module M0Spine
def failure : Client Reply := fail Reply Discarded
def faults : prod (Fault, Fault, Fault, Fault, Fault, Fault) :=
  tuple (Noscript, Busy, Oom, Network, Http, Discarded)
''')
single("generic-script", '''module M0Spine
def generic : (0 A : Type 0) -> A -> Script A (tag b"counter") :=
  fun (0 A : Type 0) (value : A) => pure A (tag b"counter") value
''')
shared = 'module Data.Shared\ndef shared : Nat := 7'
check("diamond-import", {
    "Data/Shared.tet": shared,
    "Left.tet": 'module Left\nimport Data.Shared\ndef left : Nat := shared',
    "Right.tet": 'module Right\nimport Data.Shared\ndef right : Nat := shared',
    "M0Spine.tet": 'module M0Spine\nimport Left\nimport Right\ndef main : Nat := natAdd left right'})
check("sibling-isolation", {
    "Left.tet": 'module Left\ndef secret : Nat := 1',
    "Right.tet": 'module Right\ndef leak : Nat := secret',
    "M0Spine.tet": 'module M0Spine\nimport Left\nimport Right'}, "unbound: secret")
check("import-collision", {
    "Left.tet": 'module Left\ndef value : Nat := 1',
    "Right.tet": 'module Right\ndef value : Nat := 1',
    "M0Spine.tet": 'module M0Spine\nimport Left\nimport Right'}, "DUPLICATE value")
check("cycle", {"M0Spine.tet": 'module M0Spine\nimport Other',
                "Other.tet": 'module Other\nimport M0Spine'}, "IMPORT-CYCLE")
check("import-schema", {
    "Data/Keys.tet": 'module Data.Keys\nschema hits : String -> Key (Str Int64) tag b"counter"',
    "M0Spine.tet": SPINE.replace('schema hits : String -> Key (Str Int64) tag b"counter"', 'import Data.Keys')})

# Late or malformed headers must be refused, not demoted to term tokens.
single("late-schema", SPINE + '\nschema late : String -> Key List tag b"other"', "SYNTAX")
single("late-import", SPINE + '\nimport Absent', "SYNTAX")
single("malformed-schema",
       'module M0Spine\nschema hits : Bytes -> Key (Str Int64) tag b"counter"\n', "SYNTAX")

# Both header words are headers only at a declaration position, so a local
# binder may carry either name.
single("binder-named-schema",
       SPINE + '\ndef shade : Nat -> Nat := fun (schema : Nat) => schema\n')
single("binder-named-import",
       SPINE + '\ndef shine : Nat -> Nat := fun (import : Nat) => import\n')
# A use of such a binder stands where an operand is required, so the applied
# form checks and does not reach the late-header refusal.
single("binder-named-import-applied",
       SPINE + '\ndef useimp : (Type 0 -> Nat) -> Nat := fun (import : Type 0 -> Nat) => import Nat\n')

# An imported export is a legal local binder name; only prelude names are reserved.
check("import-shadow-binder", {
    "Data/Lib.tet": 'module Data.Lib\ndef payload : Nat := 1',
    "M0Spine.tet": '''module M0Spine
import Data.Lib
def identity : Nat -> Nat := fun (payload : Nat) => payload
def main : Nat := identity payload
'''})

# Host confinement and the 1 MiB source limit, each with a positive control.
check("host-escape", {"M0Spine.tet": 'module M0Spine\nimport Out'},
      "HOST-ESCAPE", links=(("Out.tet", "/etc/hosts"),))
check("host-symlink-inside", {
    "inner/Alias.tet": 'module Alias\ndef aliased : Nat := 1',
    "M0Spine.tet": 'module M0Spine\nimport Alias\ndef main : Nat := aliased'},
    links=(("Alias.tet", "inner/Alias.tet"),))
BIG_HEAD = 'module Big\ndef big : Nat := 0\n'
check("host-oversize", {
    "M0Spine.tet": 'module M0Spine\nimport Big',
    "Big.tet": BIG_HEAD + "\n" * (1048577 - len(BIG_HEAD))}, "HOST-OVERSIZE")
check("host-limit-edge", {
    "M0Spine.tet": 'module M0Spine\nimport Big\ndef main : Nat := big',
    "Big.tet": BIG_HEAD + "\n" * (1048576 - len(BIG_HEAD))})

if CASE_COUNT != EXPECTED_CASES:
    sys.exit(f"FAIL STAGE-B-SURFACE cases={CASE_COUNT} expected={EXPECTED_CASES}")
print(f"PASS STAGE-B-SURFACE cases={CASE_COUNT}")
