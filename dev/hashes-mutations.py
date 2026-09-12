#!/usr/bin/env python3
"""Compile Hash source mutants and require their specific failed assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/hashes_tests.exe']
OFFLINE = [sys.executable, '-P', 'dev/hashes-tests.py', '--offline']
STATIC = [sys.executable, '-P', 'dev/hashes-tests.py', '--static']
BUILD = ['dune', 'build', 'bin/tether.exe', 'dev/store_run.exe', 'dev/hashes_tests.exe']
MUTANTS = [
    ('HGET-WRITE', 'print/flags.ml', b'&& tag <> 10', b'&& true', STATIC, b'HASHES write classification'),
    ('HSET-COUNT', 'store/store.ml', b'if Keys.mem field fields then "0" else "1"', b'"1"',
     UNIT, b'FAIL HASHES-UNIT overwrite count'),
    ('HDEL-EMPTY-KEY', 'store/store.ml', b'if Keys.is_empty fields then Keys.remove key store',
     b'if Keys.is_empty fields then (if Keys.mem key store then put key (Hash []) store else store)',
     UNIT, b'FAIL HASHES-UNIT delete last field'),
    ('HINCRBY-ROUND', 'print/lua.ml', b"if s.tag == 14 then read = redis.pcall('HGET',k,text(s[2]))",
     b"if s.tag == 14 then read = string.format('%.0f',redis.pcall('HGET',k,text(s[2])) + 0)",
     OFFLINE, b'HASHES LuaJIT reply'),
    ('INTERP-ERR-TAG', 'store/interp.ml', b'data "Reply" 4 [bytes (Store.message e)]',
     b'data "Reply" 2 [bytes (Store.message e)]',
     UNIT, b'FAIL HASHES-UNIT hset wrong type stops client'),
    ('HASH-FAULT-MESSAGE', 'store/store.ml', b'| Hash_not_integer -> "ERR hash value is not an integer"',
     b'| Hash_not_integer -> "ERR value is not an integer or out of range"',
     OFFLINE, b'HASHES store reply'),
]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-hashes-mutants-') as temporary:
        root = Path(temporary) / 'root'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '__pycache__'))
        run(root, BUILD)
        run(root, UNIT, marker=b'PASS HASHES-UNIT')
        run(root, OFFLINE, marker=b'PASS HASHES-ORACLES')
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
        run(root, UNIT, marker=b'PASS HASHES-UNIT')
        restored += 1
        run(root, OFFLINE, marker=b'PASS HASHES-ORACLES')
        restored += 1
        if survivors:
            raise AssertionError('SURVIVED ' + '; '.join(survivors))
        print(f'PASS HASHES-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL HASHES-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
