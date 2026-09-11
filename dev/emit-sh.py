#!/usr/bin/env python3
"""Emit a checked straight-line Client Reply as Bash and per-script byte carriers."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tether_check", ROOT / "dev/check.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def emit(source_root, path, entry, output, fuel=1000000):
    binary = ROOT / "_build/default/dev/sh_emit.exe"
    if not binary.is_file():
        print("EMIT build dev/sh_emit.exe first", file=sys.stderr)
        return 2
    rows = []
    code = checker.check(source_root, path, command=[str(binary), path, entry, str(fuel)],
                         receive=rows.append)
    if code:
        return code
    shell = None
    artifacts = []
    client = None
    keys = {}
    for row in rows:
        fields = row.rstrip(b"\n").split(b" ")
        if fields[0] == b"SH" and len(fields) == 2:
            shell = bytes.fromhex(fields[1].decode("ascii"))
        elif fields[0] == b"CLIENT" and len(fields) >= 2 and client is None:
            client = {"version": 1, "answer": int(fields[1]),
                      "invokes": [name.decode("ascii") for name in fields[2:]]}
        elif fields[0] == b"KEYS" and len(fields) >= 2:
            keys[fields[1].decode("ascii")] = [bytes.fromhex(k.decode("ascii")).decode("ascii")
                                              for k in fields[2:]]
        elif fields[0] == b"ARTIFACT" and len(fields) == 5:
            _, name, sha1, body, wasm = fields
            artifacts.append((name.decode("ascii"), sha1.decode("ascii"),
                              bytes.fromhex(body.decode("ascii")),
                              bytes.fromhex(wasm.decode("ascii"))))
        else:
            print("EMIT invalid compiler response", file=sys.stderr)
            return 2
    if shell is None or client is None or set(keys) != {a[0] for a in artifacts}:
        print("EMIT missing compiler artifacts", file=sys.stderr)
        return 2
    # Require a fresh destination so stale bodies or symlinks cannot join the output.
    output.mkdir(parents=True, exist_ok=False)
    (output / "prog.sh").write_bytes(shell)
    (output / "prog.sh").chmod(0o755)
    manifest = []
    for index, (name, sha1, body, wasm) in enumerate(artifacts):
        stem = f"body-{index}"
        (output / (stem + ".lua")).write_bytes(body)
        (output / (stem + ".wasm")).write_bytes(wasm)
        manifest.append({"entry": name, "sha1": sha1, "stem": stem, "keys": keys[name]})
    (output / "scripts.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "client.json").write_text(json.dumps(client, indent=2) + "\n")
    print(f"PASS SH-EMIT entry={entry} bodies={len(artifacts)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("path")
    parser.add_argument("--entry", default="main")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--fuel", type=int, default=1000000)
    args = parser.parse_args()
    try:
        sys.exit(emit(args.root, args.path, args.entry, args.output, args.fuel))
    except (OSError, ValueError) as error:
        print(f"EMIT {error}", file=sys.stderr)
        sys.exit(2)
