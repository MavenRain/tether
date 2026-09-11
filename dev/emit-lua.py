#!/usr/bin/env python3
"""Emit one checked Script Reply and its Wasm byte carrier for Stage C."""
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
    binary = ROOT / "_build/default/dev/lua_emit.exe"
    if not binary.is_file():
        print("EMIT build dev/lua_emit.exe first", file=sys.stderr)
        return 2
    rows = []
    code = checker.check(source_root, path, command=[str(binary), path, entry, str(fuel)],
                         receive=rows.append)
    if code:
        return code
    fields = {}
    keys = []
    for row in rows:
        name, _, value = row.rstrip(b"\n").partition(b" ")
        if name == b"KEY":
            keys.append(value.decode("ascii"))
        else:
            fields[name] = value
    output.mkdir(parents=True, exist_ok=True)
    (output / "script.lua").write_bytes(bytes.fromhex(fields[b"LUA"].decode("ascii")))
    (output / "body.wasm").write_bytes(bytes.fromhex(fields[b"WASM"].decode("ascii")))
    (output / "script.json").write_text(json.dumps({
        "entry": entry, "sha1": fields[b"SHA1"].decode("ascii"),
        "no_writes": fields[b"FLAGS"] == b"no-writes=1", "keys_hex": keys,
    }, indent=2) + "\n")
    print(f"PASS LUA-EMIT entry={entry} keys={len(keys)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("path")
    parser.add_argument("--entry", default="counter")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--fuel", type=int, default=1000000)
    args = parser.parse_args()
    sys.exit(emit(args.root, args.path, args.entry, args.output, args.fuel))
