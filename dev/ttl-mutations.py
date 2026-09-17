#!/usr/bin/env python3
"""Require expiry faults to fail their intended assertions after compiling."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/ttl_tests.exe']
UNIT = ['_build/default/dev/ttl_tests.exe']


def probe(name):
    return [sys.executable, '-P', 'dev/ttl-tests.py', '--probe', name]


MUTANTS = [
    ('CLOCK-BOUNDARY', 'store/store.ml', b'if deadline < now then remove', b'if deadline <= now then remove', UNIT, b'FAIL TTL-UNIT zero lifetime at deadline'),
    ('EXPIRE-SCALE', 'store/store.ml', b'Int64.mul amount 1000L', b'Int64.mul amount 100L', UNIT, b'FAIL TTL-UNIT seconds scale'),
    ('TTL-ROUNDING', 'store/store.ml', b'Int64.rem ms 1000L >= 500L', b'Int64.rem ms 1000L > 500L', UNIT, b'FAIL TTL-UNIT round half up'),
    ('TTL-MISSING', 'store/store.ml', b'if exists key store = "0" then -2L', b'if exists key store = "0" then -1L', UNIT, b'FAIL TTL-UNIT expiry after deadline'),
    ('SET-EXPIRY', 'store/store.ml', b'put key (Str value) (remove key store)', b'put key (Str value) store', UNIT, b'FAIL TTL-UNIT set clears expiry'),
    ('PERSIST-EXPIRY', 'store/store.ml', b'(if Keys.mem key store.deadlines then "1" else "0"), { store with deadlines = Keys.remove key store.deadlines }', b'(if Keys.mem key store.deadlines then "1" else "0"), store', UNIT, b'FAIL TTL-UNIT persist result'),
    ('STORE-REPLY-RANGE', 'store/store.ml', b'if value >= 9007199254740992L', b'if value > 9007199254740993L', UNIT, b'FAIL TTL-UNIT rounded reply refused'),
    ('INTERPRETER-UNIT', 'store/interp.ml', b'~seconds:(tag = 39 || tag = 44)', b'~seconds:(tag = 40 || tag = 44)', probe('seconds'), b'TTL interpreter reply'),
    ('LUA-UNIT', 'print/lua.ml', b"[39]='EXPIRE'", b"[39]='PEXPIRE'", probe('seconds'), b'TWIN expiry mismatch'),
    ('LUA-REPLY-RANGE', 'print/lua.ml', b'got >= 9007199254740992', b'got > 9007199254740992', probe('inexact'), b'TWIN reply kind string wanted status'),
    ('READ-FLAG', 'print/flags.ml', b' && tag <> 41', b'', probe('ttlMissing'), b'TTL write classification'),
    ('WRITE-FLAG', 'print/flags.ml', b'tag <> 0 && tag <> 2', b'tag <> 39 && tag <> 0 && tag <> 2', probe('expireMissing'), b'TTL write classification'),
    ('TWIN-SCALE', 'dev/lua-store.lua', b"amount .. '000'", b"amount .. '00'", probe('seconds'), b'TWIN expiry mismatch'),
]
CONTROLS = [(UNIT, b'PASS TTL-UNIT cases=146')] + [(probe(name), ('PASS TTL-PROBE ' + name).encode())
    for name in ('seconds', 'inexact', 'ttlMissing', 'expireMissing')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=120)
    if result.returncode != code or (marker is not None and marker not in result.stdout + result.stderr):
        raise AssertionError(f'{args}: exit={result.returncode}\n{result.stdout!r}\n{result.stderr!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-ttl-mutations-') as temporary:
        root = Path(temporary) / 'root'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '.kanonx', '.kanon-replies', '__pycache__'))
        run(root, BUILD)
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
        killed = 0
        for name, relative, old, new, test, marker in MUTANTS:
            path = root / relative
            original = path.read_bytes()
            if original.count(old) != 1:
                raise AssertionError('Mutation anchor ' + name)
            try:
                path.write_bytes(original.replace(old, new, 1))
                run(root, BUILD)
                run(root, test, code=1, marker=marker)
                killed += 1
                print(f'KILLED {name} by {marker.decode()}', flush=True)
            finally:
                path.write_bytes(original)
        run(root, BUILD)
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
        if killed != len(MUTANTS) or killed != 13 or len(CONTROLS) != 5:
            raise AssertionError('TTL mutation inventory')
        print(f'PASS TTL-MUTATIONS killed={killed} survived=0 restored={len(CONTROLS)}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL TTL-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
