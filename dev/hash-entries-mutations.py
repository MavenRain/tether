#!/usr/bin/env python3
"""Require compiled HGETALL mutants to fail at their intended assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/hash_entries_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/hash_entries_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/hash-entries-tests.py', '--probe', entry]


MUTANTS = [
    ('ENTRIES-ORDER', 'store/store.ml', b'(fun (f, v) -> [f; v]) (Keys.bindings fields)',
     b'(fun (f, v) -> [f; v]) (List.rev (Keys.bindings fields))', UNIT, b'FAIL HASH-ENTRIES-UNIT pair order'),
    ('ENTRIES-PAIR', 'store/store.ml', b'(fun (f, v) -> [f; v])', b'(fun (f, v) -> [v; f])',
     UNIT, b'FAIL HASH-ENTRIES-UNIT pair order'),
    ('ENTRIES-STATE', 'store/interp.ml', b'keep ((if tag = 28 then Store.smembers else Store.hgetall) key store)',
     b'Result.map (fun ss -> ss, Store.empty) ((if tag = 28 then Store.smembers else Store.hgetall) key store)',
     UNIT, b'FAIL HASH-ENTRIES-UNIT missing'),
    ('ENTRIES-WRITE', 'print/flags.ml', b'&& tag <> 29', b'&& true', probe('all'), b'HASH-ENTRIES write classification'),
    ('ENTRIES-BRANCH', 'print/flags.ml', b'&& tag <> 29', b'&& tag <> 11 && tag <> 29',
     probe('branch'), b'HASH-ENTRIES write classification'),
    ('LUA-FIELD-SORT', 'print/lua.ml', b'return byte_less(got[a],got[b])', b'return byte_less(got[b],got[a])',
     probe('all'), b'HASH-ENTRIES LuaJIT field/value order'),
    ('LUA-PAIR-STRIDE', 'print/lua.ml', b's.tag == 29 and 2 or 1', b's.tag == 29 and 1 or 1',
     probe('all'), b'HASH-ENTRIES LuaJIT field/value order'),
    ('LUA-FIELD-BYTES', 'print/lua.ml', b'return x < y', b'return x > y',
     probe('all'), b'HASH-ENTRIES LuaJIT field/value order'),
    ('LUA-FIELD-PREFIX', 'print/lua.ml', b'return #a < #b', b'return #a > #b',
     probe('all'), b'HASH-ENTRIES LuaJIT field/value order'),
    ('LUA-ENTRIES-ARRAY', 'print/lua.ml', b'r = {tag=5,rs}', b'r = {tag=0,rs}',
     probe('all'), b'TWIN reply kind nil wanted array'),
    ('LUA-ENTRIES-BULK', 'print/lua.ml', b'{tag=2,bytes(got[i])}', b'{tag=3,bytes(got[i])}',
     probe('value'), b'TWIN reply kind status wanted string'),
]
CONTROLS = [(UNIT, b'PASS HASH-ENTRIES-UNIT cases=16'),
            (probe('all'), b'PASS HASH-ENTRIES-PROBE entry=all cases=11'),
            (probe('branch'), b'PASS HASH-ENTRIES-PROBE entry=branch cases=1'),
            (probe('value'), b'PASS HASH-ENTRIES-PROBE entry=value cases=2')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-hash-entries-mutants-') as temporary:
        root = Path(temporary) / 'root'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '.kanonx', '__pycache__'))
        run(root, BUILD)
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
        killed, survivors = 0, []
        for name, relative, old, new, test, marker in MUTANTS:
            path = root / relative
            original = path.read_bytes()
            require_anchor = original.count(old) == 1
            if not require_anchor:
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
        if survivors or killed != len(MUTANTS) or killed != 11 or restored != 4:
            raise AssertionError(f'Mutation inventory killed={killed} restored={restored} survivors={survivors}')
        print(f'PASS HASH-ENTRIES-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL HASH-ENTRIES-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
