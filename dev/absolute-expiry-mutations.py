#!/usr/bin/env python3
"""Require absolute-expiry defects to fail their intended runtime assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/absolute_expiry_tests.exe']
UNIT = ['_build/default/dev/absolute_expiry_tests.exe']


def probe(name):
    return [sys.executable, '-P', 'dev/absolute-expiry-tests.py', '--probe', name]


MUTANTS = [
    ('STORE-AT-BASE', 'store/store.ml', b'(if absolute then 0L else store.now)', b'store.now', UNIT, b'FAIL ABSOLUTE-UNIT absolute milliseconds'),
    ('STORE-TIME-BASE', 'store/store.ml', b'if absolute then t else Int64.sub t store.now', b'Int64.sub t store.now', UNIT, b'FAIL ABSOLUTE-UNIT absolute milliseconds'),
    ('INTERPRETER-AT', 'store/interp.ml', b'~absolute:(tag >= 44)', b'~absolute:false', probe('clock'), b'TTL interpreter reply'),
    ('INTERPRETER-TIME', 'store/interp.ml', b'~absolute:(tag >= 46)', b'~absolute:false', probe('clock'), b'TTL interpreter reply'),
    ('LUA-AT', 'print/lua.ml', b"[44]='EXPIREAT'", b"[44]='PEXPIREAT'", probe('seconds'), b'TWIN expiry mismatch'),
    ('LUA-PAT', 'print/lua.ml', b"[45]='PEXPIREAT'", b"[45]='EXPIREAT'", probe('millis'), b'TWIN expiry mismatch'),
    ('LUA-TIME', 'print/lua.ml', b"[46]='EXPIRETIME'", b"[46]='PEXPIRETIME'", probe('seconds'), b'TTL LuaJIT reply'),
    ('LUA-PTIME', 'print/lua.ml', b"[47]='PEXPIRETIME'", b"[47]='EXPIRETIME'", probe('millis'), b'TTL LuaJIT reply'),
    ('READ-TIME-FLAG', 'print/flags.ml', b' && tag <> 46', b'', probe('timeMissing'), b'TTL write classification'),
    ('READ-PTIME-FLAG', 'print/flags.ml', b' && tag <> 47', b'', probe('ptimeMissing'), b'TTL write classification'),
    ('WRITE-AT-FLAG', 'print/flags.ml', b'tag <> 0 && tag <> 2', b'tag <> 44 && tag <> 0 && tag <> 2', probe('atMissing'), b'TTL write classification'),
    ('WRITE-PAT-FLAG', 'print/flags.ml', b'tag <> 0 && tag <> 2', b'tag <> 45 && tag <> 0 && tag <> 2', probe('patMissing'), b'TTL write classification'),
    ('TWIN-AT-BASE', 'dev/lua-store.lua', b"add(absolute and '0' or now, duration)", b'add(now, duration)', probe('clock'), b'TWIN expiry mismatch'),
    ('TWIN-TIME-BASE', 'dev/lua-store.lua', b"absolute and deadlines[key] or add(deadlines[key], now == '0' and '0' or '-' .. now)", b"add(deadlines[key], now == '0' and '0' or '-' .. now)", probe('clock'), b'TTL LuaJIT reply'),
]
CONTROLS = [(UNIT, b'PASS ABSOLUTE-UNIT cases=162')] + [(probe(name), ('PASS ABSOLUTE-PROBE ' + name).encode())
    for name in ('clock', 'seconds', 'millis', 'timeMissing', 'ptimeMissing', 'atMissing', 'patMissing')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=120)
    if result.returncode != code or (marker is not None and marker not in result.stdout + result.stderr):
        raise AssertionError(f'{args}: exit={result.returncode}\n{result.stdout!r}\n{result.stderr!r}')


def main():
    if len(MUTANTS) != 14 or len(CONTROLS) != 8:
        raise AssertionError('Absolute expiry mutation inventory')
    with tempfile.TemporaryDirectory(prefix='tether-absolute-mutations-') as temporary:
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
        if killed != len(MUTANTS):
            raise AssertionError('Absolute expiry survivor')
        print(f'PASS ABSOLUTE-MUTATIONS killed={killed} survived=0 restored={len(CONTROLS)}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL ABSOLUTE-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
