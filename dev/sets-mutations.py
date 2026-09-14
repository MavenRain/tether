#!/usr/bin/env python3
"""Compile Set mutants and require their specific failed assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/sets_tests.exe']
OFFLINE = [sys.executable, '-P', 'dev/sets-tests.py', '--offline']
STATIC = [sys.executable, '-P', 'dev/sets-tests.py', '--static']
BUILD = ['dune', 'build', 'bin/tether.exe', 'dev/store_run.exe', 'dev/sets_tests.exe']
MUTANTS = [
    ('SADD-COUNT', 'store/store.ml', b'let sadd = change_set Members.add',
     b'let sadd key member store = Result.map (fun (_count, after) -> "1", after) (change_set Members.add key member store)',
     UNIT, b'FAIL SETS-UNIT duplicate count'),
    ('SREM-EMPTY-KEY', 'store/store.ml', b'~empty:(Members.is_empty values)',
     b'~empty:false',
     UNIT, b'FAIL SETS-UNIT remove last member'),
    ('SISMEMBER-WRITE', 'print/flags.ml', b'&& tag <> 17', b'&& true', STATIC, b'SETS write classification'),
    ('SCARD-WRITE', 'print/flags.ml', b'&& tag <> 18', b'&& true', STATIC, b'SETS write classification'),
    ('SADD-READONLY', 'print/flags.ml', b'&& tag <> 17', b'&& tag <> 15 && tag <> 17',
     STATIC, b'SETS write classification'),
    ('SET-LUA-COUNT', 'print/lua.ml', b"bytes(string.format('%d',got))", b"bytes('0')",
     OFFLINE, b'SETS LuaJIT reply'),
    ('SET-ERR-TAG', 'store/interp.ml', b'data "Reply" 4 [bytes (Store.message e)]',
     b'data "Reply" 2 [bytes (Store.message e)]', UNIT, b'FAIL SETS-UNIT sadd wrong type stops client'),
    ('SET-LUA-ERR-TAG', 'print/lua.ml',
     b"if type(got) == 'table' and got.err then r = {tag=4,bytes(got.err)}\n"
     b"      elseif type(got) ~= 'number' then",
     b"if type(got) == 'table' and got.err then r = {tag=2,bytes(got.err)}\n"
     b"      elseif type(got) ~= 'number' then",
     OFFLINE, b'TWIN reply kind string wanted status'),
]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-sets-mutants-') as temporary:
        root = Path(temporary) / 'root'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '__pycache__'))
        run(root, BUILD)
        run(root, UNIT, marker=b'PASS SETS-UNIT')
        run(root, OFFLINE, marker=b'PASS SETS-ORACLES')
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
        run(root, UNIT, marker=b'PASS SETS-UNIT')
        restored += 1
        run(root, OFFLINE, marker=b'PASS SETS-ORACLES')
        restored += 1
        if survivors:
            raise AssertionError('SURVIVED ' + '; '.join(survivors))
        print(f'PASS SETS-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL SETS-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
