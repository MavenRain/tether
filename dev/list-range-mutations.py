#!/usr/bin/env python3
"""Compile LRANGE mutants and require their intended assertion failures."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/list_range_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/list_range_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/list-range-tests.py', '--probe', entry]


MUTANTS = [
    ('RANGE-END', 'store/store.ml', b'i >= first && i <= last', b'i >= first && i < last',
     UNIT, b'FAIL LIST-RANGE-UNIT range all'),
    ('ARRAY-ORDER', 'store/interp.ml', b'ss (data "Replies" 0 [])', b'(List.rev ss) (data "Replies" 0 [])',
     UNIT, b'FAIL LIST-RANGE-UNIT range all'),
    ('ARRAY-BULK', 'store/interp.ml', b'[scalar 2 s; rs]', b'[scalar 3 s; rs]',
     UNIT, b'FAIL LIST-RANGE-UNIT range all'),
    ('RANGE-STATE', 'store/interp.ml', b'keep (Store.lrange key i j store)',
     b'Result.map (fun ss -> ss, Store.empty) (Store.lrange key i j store)',
     UNIT, b'FAIL LIST-RANGE-UNIT range all'),
    ('LRANGE-WRITE', 'print/flags.ml', b'&& tag <> 27', b'&& true',
     probe('all'), b'LIST-RANGE write classification'),
    ('BRANCH-READONLY', 'print/flags.ml', b'&& tag <> 27', b'&& tag <> 26 && tag <> 27',
     probe('branch'), b'LIST-RANGE write classification'),
    ('LUA-ARRAY-ORDER', 'print/lua.ml', b'for n = #order, 1, -1 do', b'for n = 1, #order do',
     probe('all'), b'LISTS LuaJIT reply'),
    ('LUA-RANGE-STOP', 'print/lua.ml', b"or 'LRANGE',k,text(s[2][1]),text(s[3][1]))",
     b"or 'LRANGE',k,text(s[2][1]),text(s[2][1]))", probe('tail'), b'LISTS LuaJIT reply'),
    ('LUA-ARRAY-TAG', 'print/lua.ml', b'r = {tag=5,rs}', b'r = {tag=0,rs}',
     probe('all'), b'TWIN reply kind nil wanted array'),
    ('LUA-ARRAY-ELEMENT', 'print/lua.ml', b'{tag=2,bytes(got[i])}', b'{tag=3,bytes(got[i])}',
     probe('head'), b'TWIN reply kind status wanted string'),
    ('LUA-ERR-TAG', 'print/lua.ml',
     b"      if type(got) == 'table' and got.err then r = {tag=4,bytes(got.err)}\n"
     b"      elseif type(got) == 'table' and got.ok then r = {tag=3,bytes(got.ok)}\n"
     b'      elseif s.tag >= 27 and s.tag <= 34 then',
     b"      if type(got) == 'table' and got.err then r = {tag=2,bytes(got.err)}\n"
     b"      elseif type(got) == 'table' and got.ok then r = {tag=3,bytes(got.ok)}\n"
     b'      elseif s.tag >= 27 and s.tag <= 34 then',
     probe('all'), b'TWIN reply kind string wanted status'),
]

CONTROLS = [
    (UNIT, b'PASS LIST-RANGE-UNIT cases=101'),
    (probe('all'), b'PASS LIST-RANGE-PROBE entry=all cases=9'),
    (probe('branch'), b'PASS LIST-RANGE-PROBE entry=branch cases=1'),
    (probe('tail'), b'PASS LIST-RANGE-PROBE entry=tail cases=2'),
    (probe('head'), b'PASS LIST-RANGE-PROBE entry=head cases=3'),
]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-list-range-mutants-') as temporary:
        root = Path(temporary) / 'root'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '.kanonx', '__pycache__'))
        run(root, BUILD)
        # Each control carries its own complete row, so a control that stops
        # checking what it names cannot satisfy a shared prefix.
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
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
        restored = 0
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
            restored += 1
        if survivors:
            raise AssertionError('SURVIVED ' + '; '.join(survivors))
        if killed != len(MUTANTS) or killed != 11 or restored != 5:
            raise AssertionError('Mutation inventory')
        print(f'PASS LIST-RANGE-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-RANGE-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
