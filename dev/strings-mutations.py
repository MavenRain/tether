#!/usr/bin/env python3
"""Compile real source mutations in a disposable tree and require named failures."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/strings_tests.exe']
OFFLINE = [sys.executable, '-P', 'dev/strings-tests.py', '--offline']
STATIC = [sys.executable, '-P', 'dev/strings-tests.py', '--static']
BUILD = ['dune', 'build', 'bin/tether.exe', 'dev/store_run.exe', 'dev/strings_tests.exe']
MUTANTS = [
    ('EXISTS-WRITE', 'print/flags.ml', b'tag <> 2 && tag <> 8', b'tag <> 2',
     STATIC, b'STRINGS write classification'),
    ('DECIMAL-ROUND', 'print/lua.ml', b'bytes(read)', b"bytes(string.format('%.0f',read + 0))",
     OFFLINE, b'STRINGS LuaJIT reply'),
    ('NEGATIVE-OVERFLOW', 'store/store.ml', b'amount < 0L', b'false',
     UNIT, b'FAIL STRINGS-UNIT overflow'),
    ('DEL-KEEPS-KEY', 'store/store.ml', b'exists key store, remove key store', b'exists key store, store',
     UNIT, b'FAIL STRINGS-UNIT delete'),
]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-strings-mutants-') as temporary:
        root = Path(temporary) / 'root'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '__pycache__'))
        run(root, BUILD)
        run(root, UNIT, marker=b'PASS STRINGS-UNIT')
        run(root, OFFLINE, marker=b'PASS STRINGS-ORACLES')
        killed = 0
        survivors = []
        for name, relative, old, new, test, marker in MUTANTS:
            path = root / relative
            original = path.read_bytes()
            if original.count(old) != 1:
                raise AssertionError('Mutation anchor ' + name)
            try:
                path.write_bytes(original.replace(old, new, 1))
                run(root, BUILD)
                try:
                    run(root, test, 1, marker)
                except AssertionError as error:
                    survivors.append(f'{name}: {error}')
                else:
                    killed += 1
                    print(f'KILLED {name} by {marker.decode()}', flush=True)
            finally:
                path.write_bytes(original)
        restored = 0
        run(root, BUILD)
        run(root, UNIT, marker=b'PASS STRINGS-UNIT')
        restored += 1
        run(root, OFFLINE, marker=b'PASS STRINGS-ORACLES')
        restored += 1
        if survivors:
            raise AssertionError('SURVIVED ' + '; '.join(survivors))
        print(f'PASS STRINGS-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL STRINGS-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
