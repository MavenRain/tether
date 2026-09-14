#!/usr/bin/env python3
"""Require compiled SMEMBERS mutants to fail at their intended assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/set_members_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/set_members_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/set-members-tests.py', '--probe', entry]


MUTANTS = [
    ('MEMBERS-ORDER', 'store/store.ml', b'Result.map Members.elements (members key store)',
     b'Result.map (fun ms -> List.rev (Members.elements ms)) (members key store)', UNIT, b'FAIL SET-MEMBERS-UNIT unique order'),
    ('MEMBERS-STATE', 'store/interp.ml', b'keep ((if tag = 28 then Store.smembers else Store.hgetall) key store)',
     b'Result.map (fun ss -> ss, Store.empty) ((if tag = 28 then Store.smembers else Store.hgetall) key store)', UNIT, b'FAIL SET-MEMBERS-UNIT missing'),
    ('MEMBERS-WRITE', 'print/flags.ml', b'&& tag <> 28', b'&& true', probe('all'), b'SET-MEMBERS write classification'),
    ('MEMBERS-BRANCH', 'print/flags.ml', b'&& tag <> 28', b'&& tag <> 16 && tag <> 28',
     probe('branch'), b'SET-MEMBERS write classification'),
    ('LUA-MEMBERS-SORT', 'print/lua.ml', b'return byte_less(got[a],got[b])',
     b'return byte_less(got[b],got[a])', probe('all'), b'SET-MEMBERS LuaJIT member order'),
    ('LUA-BYTE-ORDER', 'print/lua.ml', b'return x < y', b'return x > y', probe('all'), b'SET-MEMBERS LuaJIT member order'),
    ('LUA-PREFIX-ORDER', 'print/lua.ml', b'return #a < #b', b'return #a > #b', probe('all'), b'SET-MEMBERS LuaJIT member order'),
    ('LUA-MEMBERS-ARRAY', 'print/lua.ml', b'r = {tag=5,rs}', b'r = {tag=0,rs}',
     probe('all'), b'TWIN reply kind nil wanted array'),
    ('LUA-MEMBERS-BULK', 'print/lua.ml', b'{tag=2,bytes(got[i])}', b'{tag=3,bytes(got[i])}',
     probe('head'), b'TWIN reply kind status wanted string'),
]
CONTROLS = [(UNIT, b'PASS SET-MEMBERS-UNIT cases=14'),
            (probe('all'), b'PASS SET-MEMBERS-PROBE entry=all cases=10'),
            (probe('branch'), b'PASS SET-MEMBERS-PROBE entry=branch cases=1'),
            (probe('head'), b'PASS SET-MEMBERS-PROBE entry=head cases=3')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-set-members-mutants-') as temporary:
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
        if survivors or killed != len(MUTANTS) or killed != 9 or restored != 4:
            raise AssertionError(f'Mutation inventory killed={killed} restored={restored} survivors={survivors}')
        print(f'PASS SET-MEMBERS-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL SET-MEMBERS-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
