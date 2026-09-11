#!/usr/bin/env python3
"""Enforce the independently owned Node and REST reply decoder files."""
from pathlib import Path
import re
import sys

TOKEN = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*|[0-9]+|[^\sA-Za-z0-9_$]")
WINDOW = 8
SIMILARITY = 0.5


def shingles(source):
    """Token windows of a file, with line comments removed."""
    tokens = TOKEN.findall(re.sub(r"//[^\n]*", "", source))
    return {tuple(tokens[index:index + WINDOW]) for index in range(max(0, len(tokens) - WINDOW + 1))}


def similarity(left, right):
    """Share of the smaller token-window set that the larger one also holds."""
    shared = len(left & right)
    return shared / min(len(left), len(right)) if left and right else 1.0


def check(root):
    node = root / 'runtime/redis-host.mjs'
    rest = root / 'runtime/rest-decode.mjs'
    twin = root / 'runtime/rest-twin.mjs'
    if node.samefile(rest) or node.read_bytes() == rest.read_bytes():
        return False
    for path, forbidden in ((node, 'rest-'), (rest, 'redis-host'), (twin, 'redis-host')):
        source = path.read_text()
        if forbidden in source or re.search(r'\b(?:eval|require)\s*\(|\bimport\s*\(', source):
            return False
    # A copied body carries the token windows of its origin, so measure the
    # overlap instead of trusting names and imports alone. Independent
    # implementations share about 0.16 of their windows, a copy about 0.98.
    if similarity(shingles(node.read_text()), shingles(rest.read_text())) >= SIMILARITY:
        return False
    return (all('export function decode(' in p.read_text() for p in (node, rest))
            and "from './rest-decode.mjs'" in twin.read_text())


if __name__ == '__main__':
    try:
        passed = check(Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).resolve().parents[1])
        print('DECODERS-SPLIT files=2' if passed else 'FAIL DECODERS-SPLIT')
        sys.exit(0 if passed else 1)
    except OSError as error:
        print(f'FAIL DECODERS-SPLIT {error}')
        sys.exit(1)
