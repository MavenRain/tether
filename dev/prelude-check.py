#!/usr/bin/env python3
"""Pin both trusted preludes without inventing an eighth line bound."""
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PATHS = {"runtime/reactor.kan", "runtime/redis.kan"}


def check(root):
    rows = [line.split() for line in (root / "dev/PRELUDES.sha256").read_text().splitlines()]
    if len(rows) != 2 or any(len(row) != 2 for row in rows):
        return "PRELUDE-INTEGRITY FAIL manifest shape", False
    if {path for _sha, path in rows} != PATHS:
        return "PRELUDE-INTEGRITY FAIL manifest inventory", False
    count = 0
    for sha, relative in rows:
        data = (root / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            return "PRELUDE-INTEGRITY FAIL " + relative, False
        count += data.count(b"\n") + int(bool(data) and not data.endswith(b"\n"))
    return f"PRELUDE-INTEGRITY lines={count} files=2 OK", True


if __name__ == "__main__":
    try:
        line, ok = check(ROOT)
    except OSError as error:
        line, ok = f"PRELUDE-INTEGRITY FAIL {error}", False
    print(line)
    sys.exit(0 if ok else 1)
