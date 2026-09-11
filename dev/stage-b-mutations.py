#!/usr/bin/env python3
"""Source mutations run only in a disposable copy of this repository."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(root, command, expected, success):
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120)
    text = result.stdout + result.stderr
    if (result.returncode == 0) != success or expected not in text:
        sys.exit(f"FAIL STAGE-B-MUTATIONS {command} exit={result.returncode}\n{text}")
    return text


def kernel_field(text):
    return next((token for token in text.split() if token.startswith("kernel=")), "kernel=absent")


def lua_count(text):
    field = next((token for token in text.split() if token.startswith("lua=")), "lua=0/0")
    return int(field[len("lua="):].split("/")[0])


with tempfile.TemporaryDirectory(prefix="tether-stage-b-") as directory:
    root = Path(directory) / "tree"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
        "_build", ".gatework", ".kanon-exec", ".kanon-wait", "__pycache__"))
    run(root, ["sh", "dev/r0-count.sh"], "R0-COUNT", True)
    shape = root / "vendor/kanon/lib/shape.ml"
    original = shape.read_bytes()
    old = b'let declared : string list = [ "SPi"; "SColl"; "SPar"; "SMu"; "SNu" ]'
    if original.count(old) != 1:
        sys.exit("FAIL STAGE-B-MUTATIONS sixth-shape anchor")
    shape.write_bytes(original.replace(old, old[:-2] + b'; "SSixth" ]'))
    run(root, ["sh", "dev/r0-count.sh"], "built counts differ", False)
    print("KILLED SIXTH-SHAPE by rebuilt R0-COUNT", flush=True)
    shape.write_bytes(original)
    run(root, ["sh", "dev/r0-count.sh"], "R0-COUNT", True)
    # The house gate must deny an exception site in the surface sources.
    run(root, ["sh", "dev/house.sh"], "PASS HOUSE", True)
    schema = root / "surface/schema.ml"
    original = schema.read_bytes()
    # The banned token is assembled here so it never appears in a checked source.
    schema.write_bytes(original + b'\nlet _mutant = ' + b'fail' + b'with "house mutant"\n')
    run(root, ["sh", "dev/house.sh"], "gate failed", False)
    print("KILLED HOUSE-EXCEPTION by panicscan", flush=True)
    schema.write_bytes(original)
    run(root, ["sh", "dev/house.sh"], "PASS HOUSE", True)
    nested = root / ".gatework/nested.kan"
    nested.parent.mkdir(exist_ok=True)
    inline = ('mu Script (0 A : Type 0) : Type 0 := '
              '| pure : A -> Script A | step : (Nat -> Script A) -> Script A\n')
    nested.write_text(inline)
    command = [str(root / "_build/default/vendor/kanon/bin/kanon.exe"), "check", str(nested)]
    run(root, command, "", True)
    nested.write_text('mu Op (0 A : Type 0) : Type 0 := | op : A -> Op A\n'
                      'mu Script (0 A : Type 0) : Type 0 := '
                      '| nested : Op (Script A) -> Script A\n')
    run(root, command, "not strictly positive", False)
    print("KILLED NESTED-OP by inherited positivity", flush=True)
    nested.write_text(inline)
    run(root, command, "", True)
    counted = run(root, [sys.executable, "-P", "dev/trusted-lines.py"], "TRUSTED-LINES", True)
    printer = root / "print/lua.ml"
    original = printer.read_bytes()
    printer.write_bytes(original + b"\n" * 321)
    # The expectation names the overflowed Lua field itself, so a failure in
    # another group cannot satisfy this mutant.
    run(root, [sys.executable, "-P", "dev/trusted-lines.py"],
        f"lua={lua_count(counted) + 321}/320", False)
    print("KILLED LUA-BOUND by TRUSTED-LINES", flush=True)
    printer.write_bytes(original)
    run(root, [sys.executable, "-P", "dev/trusted-lines.py"], "TRUSTED-LINES", True)
    # Both counters run in one ladder, so they must report one kernel number
    # even when a trusted source has no final newline.
    order = root / "vendor/kanon/lib/order.ml"
    kept = order.read_bytes()
    order.write_bytes(kept.rstrip(b"\n"))
    python_line = run(root, [sys.executable, "-P", "dev/trusted-lines.py"], "TRUSTED-LINES", True)
    shell_line = run(root, ["zsh", "-f", "dev/inherited/trusted-lines.sh",
                            str(root / "vendor/kanon")], "TRUSTED-LINES", True)
    if kernel_field(python_line) != kernel_field(shell_line):
        sys.exit("FAIL STAGE-B-MUTATIONS counters disagree\n" + python_line + shell_line)
    print("AGREED NEWLINE-COUNT by both trusted-line counters", flush=True)
    order.write_bytes(kept)
    run(root, [sys.executable, "-P", "dev/trusted-lines.py"], "TRUSTED-LINES", True)
    encoder = root / "vendor/kanon/wasm/gc_encode.ml"
    original = encoder.read_bytes()
    encoder.unlink()
    run(root, [sys.executable, "-P", "dev/trusted-lines.py"], "TRUSTED-LINES FAIL", False)
    print("KILLED MISSING-ENCODER by TRUSTED-LINES", flush=True)
    encoder.write_bytes(original)
    run(root, [sys.executable, "-P", "dev/trusted-lines.py"], "TRUSTED-LINES", True)
print("PASS STAGE-B-MUTATIONS killed=5 restored=1")
