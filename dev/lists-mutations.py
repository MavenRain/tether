#!/usr/bin/env python3
"""Compile List mutants and require failures at the intended assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/lists_tests.exe']
OFFLINE = [sys.executable, '-P', 'dev/lists-tests.py', '--offline']
ARTIFACTS = [sys.executable, '-P', 'dev/lists-tests.py', '--artifacts']
STATIC = [sys.executable, '-P', 'dev/lists-tests.py', '--static']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/lists_tests.exe']
MUTANTS = [
    ('RIGHT-ORIENTATION', 'store/store.ml', b'Right -> List.rev', b'Right -> Fun.id',
     UNIT, b'FAIL LISTS-UNIT right push order'),
    ('RPOP-REMAINDER', 'store/store.ml', b'List (orient side rest)', b'List rest',
     UNIT, b'FAIL LISTS-UNIT right pop order'),
    ('POP-EMPTY-KEY', 'store/store.ml', b'~empty:(rest = [])', b'~empty:false',
     UNIT, b'FAIL LISTS-UNIT left deletes last key'),
    ('LLEN-COUNT', 'store/store.ml', b'Ok (string_of_int (List.length values))',
     b'Ok (string_of_int (0 * List.length values))',
     UNIT, b'FAIL LISTS-UNIT length includes duplicates'),
    ('LLEN-WRITE', 'print/flags.ml', b'&& tag <> 23', b'&& true',
     ARTIFACTS, b'LISTS write classification'),
    ('LPOP-READONLY', 'print/flags.ml', b'&& tag <> 23', b'&& tag <> 21 && tag <> 23',
     ARTIFACTS, b'LISTS write classification'),
    ('LIST-LUA-DIRECTION', 'print/lua.ml', b"[19]='LPUSH',[20]='RPUSH'",
     b"[19]='RPUSH',[20]='LPUSH'", OFFLINE, b'TWIN list order mismatch'),
    ('LIST-LUA-NIL', 'print/lua.ml', b"elseif got == false then r = {tag=0}",
     b"elseif got == false then r = {tag=2,bytes('')}", OFFLINE, b'TWIN reply kind string wanted nil'),
    ('LIST-ERR-TAG', 'store/interp.ml', b'data "Reply" 4 [bytes (Store.message e)]',
     b'data "Reply" 2 [bytes (Store.message e)]', UNIT, b'FAIL LISTS-UNIT lpush wrong type stops client'),
]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-lists-mutants-') as temporary:
        root = Path(temporary) / 'root'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '__pycache__'))
        run(root, BUILD)
        run(root, UNIT, marker=b'PASS LISTS-UNIT')
        run(root, OFFLINE, marker=b'PASS LISTS-ORACLES')
        run(root, STATIC, marker=b'PASS LISTS-REFUSALS')
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
        run(root, UNIT, marker=b'PASS LISTS-UNIT')
        restored += 1
        run(root, OFFLINE, marker=b'PASS LISTS-ORACLES')
        restored += 1
        if survivors:
            raise AssertionError('SURVIVED ' + '; '.join(survivors))
        print(f'PASS LISTS-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL LISTS-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
