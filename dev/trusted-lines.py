#!/usr/bin/env python3
"""Seven M0 bounds, measured from source files including blank lines."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ("shape term rules check value eval conv totality positivity global order bignum").split()
GROUPS = {
    "kernel": (4000, [f"vendor/kanon/lib/{name}.ml" for name in KERNEL]),
    "encoder": (600, ["vendor/kanon/wasm/gc_encode.ml"]),
    "lua": (320, ["print/lua.ml", "print/sha1.ml", "print/flags.ml", "print/transport.ml"]),
    "sh": (240, ["print/sh.ml"]),
    "store": (200, ["store/store.ml", "store/interp.ml"]),
    "host-node": (300, ["runtime/redis-host.mjs"]),
    "host-rest": (300, ["runtime/rest-twin.mjs", "runtime/rest-decode.mjs"]),
}


def measure(root):
    fields = []
    ok = True
    for name, (bound, paths) in GROUPS.items():
        count = 0
        # The kernel and encoder groups are also counted by the carried
        # dev/inherited/trusted-lines.sh, which uses wc -l and so counts
        # newlines only. Both legs run in one ladder, so they must agree.
        newline_only = name in ("kernel", "encoder")
        for relative in paths:
            path = root / relative
            if not path.exists() and name not in ("kernel", "encoder", "lua", "sh"):
                # The remaining implementations are due in Stage E.
                continue
            data = path.read_bytes()
            unterminated = bool(data) and not data.endswith(b"\n")
            count += data.count(b"\n") + int(unterminated and not newline_only)
        fields.append(f"{name}={count}/{bound}")
        ok = ok and count <= bound
    return "TRUSTED-LINES " + " ".join(fields) + (" OK" if ok else " FAIL"), ok


if __name__ == "__main__":
    try:
        known = {path for _bound, paths in GROUPS.values() for path in paths}
        unexpected = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "print").glob("*.ml")
                            if str(path.relative_to(ROOT)) not in known)
        if unexpected:
            print("TRUSTED-LINES FAIL uncounted printer files: " + ", ".join(unexpected))
            sys.exit(1)
        line, passed = measure(ROOT)
        print(line)
        sys.exit(0 if passed else 1)
    except OSError as error:
        print(f"TRUSTED-LINES FAIL {error}")
        sys.exit(1)
