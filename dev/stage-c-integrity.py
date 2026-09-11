#!/usr/bin/env python3
"""Mutation controls for Stage C's source inventories, in a disposable tree."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def gate(root, script, ok=True, diagnostic=" OK"):
    # Run the copied checker so its root is the disposable tree.
    result = subprocess.run([sys.executable, "-P", str(root / "dev" / script)],
                            cwd=root, capture_output=True, text=True, timeout=30)
    text = result.stdout + result.stderr
    if (result.returncode == 0) != ok or diagnostic not in text:
        sys.exit(f"FAIL STAGE-C-INTEGRITY {script} exit={result.returncode}\n{text}")


with tempfile.TemporaryDirectory(prefix="tether-c-integrity-") as directory:
    root = Path(directory)
    # bin carries its own trusted-lines bound, so the disposable tree needs it.
    for name in ("bin", "print", "store", "runtime", "dev", "vendor/kanon/lib", "vendor/kanon/wasm"):
        shutil.copytree(ROOT / name, root / name,
                        ignore=shutil.ignore_patterns("_build", ".kanon-exec", ".kanon-wait", "__pycache__"))
    gate(root, "trusted-lines.py")
    gate(root, "prelude-check.py")
    count = 0
    for relative, script, diagnostic in [
            ("print/lua.ml", "trusted-lines.py", "TRUSTED-LINES FAIL"),
            ("print/transport.ml", "trusted-lines.py", "TRUSTED-LINES FAIL"),
            ("runtime/redis.kan", "prelude-check.py", "PRELUDE-INTEGRITY FAIL")]:
        path = root / relative
        original = path.read_bytes()
        path.unlink()
        gate(root, script, False, diagnostic)
        path.write_bytes(original)
        gate(root, script)
        print("KILLED MISSING-" + path.stem.upper(), flush=True)
        count += 1
    prelude = root / "runtime/redis.kan"
    original = prelude.read_bytes()
    prelude.write_bytes(original + b"\n")
    gate(root, "prelude-check.py", False, "PRELUDE-INTEGRITY FAIL runtime/redis.kan")
    prelude.write_bytes(original)
    gate(root, "prelude-check.py")
    print("KILLED PRELUDE-GROWTH", flush=True)
    count += 1
    extra = root / "print/uncounted.ml"
    extra.write_text("let value = 0\n")
    gate(root, "trusted-lines.py", False, "uncounted implementation files")
    extra.unlink()
    gate(root, "trusted-lines.py")
    print("KILLED UNCOUNTED-PRINTER", flush=True)
    count += 1
print(f"PASS STAGE-C-INTEGRITY killed={count} restored=1")
