#!/usr/bin/env python3
"""Stage B checker host: file IO only; resolution and checking live in OCaml."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(source_root, entry, erased=False, fuel=1000000, *, command=None, receive=None):
    source_root = source_root.resolve()
    binary = ROOT / "_build/default/dev/surface_check.exe"
    if command is None and not binary.is_file():
        print("CHECK build dev/surface_check.exe first", file=sys.stderr)
        return 1
    if command is None:
        command = [str(binary), entry, str(fuel), "erased" if erased else "check"]
    with subprocess.Popen(command, stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE) as process:
        for line in process.stdout:
            if not line.startswith(b"READ "):
                if receive is None:
                    sys.stdout.buffer.write(line)
                else:
                    receive(line)
                continue
            request = line[5:].rstrip(b"\n").decode("utf-8")
            try:
                if request in ("@reactor", "@redis"):
                    path = ROOT / "runtime" / (request[1:] + ".kan")
                else:
                    path = (source_root / request).resolve()
                    if not path.is_relative_to(source_root):
                        raise ValueError("HOST-ESCAPE source leaves the selected root")
                data = path.read_bytes()
                if len(data) > 1048576:
                    raise ValueError("HOST-OVERSIZE source exceeds 1 MiB")
                response = str(len(data)).encode() + b"\n" + data
            except (OSError, ValueError) as error:
                # Name the refused request so a fixture can tell the reasons apart.
                print(f"HOST-REFUSED {request}: {error}", file=sys.stderr, flush=True)
                response = b"-1\n"
            process.stdin.write(response)
            process.stdin.flush()
        return process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("entry", help="path relative to the source root")
    parser.add_argument("--erased", action="store_true", help="print inherited erased IR")
    parser.add_argument("--fuel", type=int, default=1000000, help="kernel poll budget")
    args = parser.parse_args()
    sys.exit(check(args.root, args.entry, args.erased, args.fuel))
