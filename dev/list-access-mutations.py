#!/usr/bin/env python3
"""Compile mutants and require their intended boundary or parity failure."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/list_access_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/list_access_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/list-access-tests.py', '--probe', entry]


MUTANTS = [
    ('INDEX-NEGATIVE', 'store/store.ml', b'Int64.add (Int64.of_int (List.length values)) index',
     b'Int64.add (Int64.of_int (0 * List.length values)) index',
     UNIT, b'FAIL LIST-ACCESS-UNIT index negative'),
    ('INDEX-MISSING', 'store/store.ml', b'if values = [] then Ok None', b'if values = [] then Ok (Some "")',
     UNIT, b'FAIL LIST-ACCESS-UNIT missing index before invalid integer'),
    ('LSET-POSITION', 'store/store.ml', b'if Int64.of_int i = index then value else v', b'if Int64.of_int i <> index then value else v',
     UNIT, b'FAIL LIST-ACCESS-UNIT set first'),
    ('LTRIM-END', 'store/store.ml', b'i >= first && i <= last', b'i >= first && i < last',
     UNIT, b'FAIL LIST-ACCESS-UNIT trim inclusive'),
    ('LTRIM-EMPTY-KEY', 'store/store.ml', b'~empty:(values = [])', b'~empty:false',
     UNIT, b'FAIL LIST-ACCESS-UNIT trim reversed deletes key'),
    ('LIST-ACCESS-ERR-TAG', 'store/interp.ml', b'data "Reply" 4 [bytes (Store.message e)]',
     b'data "Reply" 2 [bytes (Store.message e)]', UNIT, b'FAIL LIST-ACCESS-UNIT set missing stops client'),
    ('LINDEX-WRITE', 'print/flags.ml', b'&& tag <> 24', b'&& true',
     probe('atHead'), b'LIST-ACCESS write classification'),
    ('LTRIM-READONLY', 'print/flags.ml', b'&& tag <> 24', b'&& tag <> 26 && tag <> 24',
     probe('branch'), b'LIST-ACCESS write classification'),
    ('LUA-INDEX', 'print/lua.ml', b"redis.pcall('LINDEX',k,text(s[2][1]))", b"redis.pcall('LINDEX',k,'0')",
     probe('atTail'), b'LISTS LuaJIT reply'),
    ('LUA-REPLACEMENT', 'print/lua.ml', b"redis.pcall('LSET',k,text(s[2][1]),text(s[3]))",
     b"redis.pcall('LSET',k,text(s[2][1]),text(s[2][1]))", probe('replace'), b'TWIN list order mismatch'),
    ('LUA-STATUS-TAG', 'print/lua.ml', b'then r = {tag=3,bytes(got.ok)}', b'then r = {tag=2,bytes(got.ok)}',
     probe('trimMiddle'), b'TWIN reply kind string wanted status'),
    ('LUA-ERR-TAG', 'print/lua.ml',
     b"next = s[3] end\n      if type(got) == 'table' and got.err then r = {tag=4,bytes(got.err)}",
     b"next = s[3] end\n      if type(got) == 'table' and got.err then r = {tag=3,bytes(got.err)}",
     probe('atHead'), b'TWIN reply kind status wanted string'),
]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-list-access-mutants-') as temporary:
        root = Path(temporary) / 'root'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '.kanonx', '__pycache__'))
        controls = [UNIT, *(probe(entry) for entry in ('atHead', 'branch', 'atTail', 'replace', 'trimMiddle'))]
        run(root, BUILD)
        for test in controls:
            run(root, test, marker=b'PASS LIST-ACCESS-')
        killed, survivors = 0, []
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
        run(root, BUILD)
        for test in controls:
            run(root, test, marker=b'PASS LIST-ACCESS-')
        if survivors:
            raise AssertionError('SURVIVED ' + '; '.join(survivors))
        require_count = len(MUTANTS)
        if killed != require_count or require_count != 12:
            raise AssertionError('Mutation inventory')
        print(f'PASS LIST-ACCESS-MUTATIONS killed={killed} survived=0 restored={len(controls)}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-ACCESS-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
