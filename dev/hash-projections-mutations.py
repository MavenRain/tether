#!/usr/bin/env python3
"""Require compiled HKEYS and HVALS mutants to fail at intended assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/hash_projections_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/hash_projections_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/hash-projections-tests.py', '--probe', entry]


MUTANTS = [
    ('PROJECTION-TAGS', 'store/interp.ml', b'if tag = 30 then fst else snd', b'if tag = 30 then snd else fst',
     UNIT, b'FAIL HASH-PROJECTIONS-UNIT projection'),
    ('PROJECTION-ORDER', 'store/store.ml', b'List.sort String.compare (List.map project', b'Fun.id (List.map project',
     UNIT, b'FAIL HASH-PROJECTIONS-UNIT projection'),
    ('KEYS-ORDER', 'store/store.ml', b'List.sort String.compare (List.map project (Keys.bindings fs))',
     b'(fun ks -> if ks = List.map fst (Keys.bindings fs) then List.rev ks else ks) (List.sort String.compare (List.map project (Keys.bindings fs)))',
     UNIT, b'FAIL HASH-PROJECTIONS-UNIT projection'),
    ('PROJECTION-DUPLICATES', 'store/store.ml', b'List.sort String.compare (List.map project', b'List.sort_uniq String.compare (List.map project',
     UNIT, b'FAIL HASH-PROJECTIONS-UNIT duplicates'),
    ('PROJECTION-STATE', 'store/interp.ml', b'keep (Store.hproject (if tag = 30 then fst else snd) key store)',
     b'Result.map (fun ss -> ss, Store.empty) (Store.hproject (if tag = 30 then fst else snd) key store)',
     UNIT, b'FAIL HASH-PROJECTIONS-UNIT missing'),
    ('KEYS-WRITE', 'print/flags.ml', b'&& tag <> 30', b'&& true', probe('keys'), b'HASH-PROJECTIONS write classification'),
    ('VALS-WRITE', 'print/flags.ml', b'&& tag <> 31', b'&& true', probe('vals'), b'HASH-PROJECTIONS write classification'),
    ('KEYS-BRANCH', 'print/flags.ml', b'&& tag <> 30', b'&& tag <> 11 && tag <> 30',
     probe('keysBranch'), b'HASH-PROJECTIONS write classification'),
    ('VALS-BRANCH', 'print/flags.ml', b'&& tag <> 31', b'&& tag <> 11 && tag <> 31',
     probe('valsBranch'), b'HASH-PROJECTIONS write classification'),
    ('LUA-KEYS', 'print/lua.ml', b"[30]='HKEYS'", b"[30]='HVALS'", probe('keys'), b'HASH-PROJECTIONS LuaJIT reply'),
    ('LUA-VALS', 'print/lua.ml', b"[31]='HVALS'", b"[31]='HKEYS'", probe('vals'), b'HASH-PROJECTIONS LuaJIT reply'),
    ('LUA-PROJECTION-SORT', 'print/lua.ml', b'return byte_less(got[a],got[b])', b'return byte_less(got[b],got[a])',
     probe('vals'), b'HASH-PROJECTIONS LuaJIT reply'),
    ('LUA-PROJECTION-BYTES', 'print/lua.ml', b'return x < y', b'return x > y', probe('keys'), b'HASH-PROJECTIONS LuaJIT reply'),
    ('LUA-PROJECTION-PREFIX', 'print/lua.ml', b'return #a < #b', b'return #a > #b', probe('keys'), b'HASH-PROJECTIONS LuaJIT reply'),
    ('LUA-PROJECTION-ARRAY', 'print/lua.ml', b'r = {tag=5,rs}', b'r = {tag=0,rs}', probe('keys'), b'TWIN reply kind nil wanted array'),
    ('LUA-PROJECTION-BULK', 'print/lua.ml', b'{tag=2,bytes(got[i])}', b'{tag=3,bytes(got[i])}',
     probe('valsHead'), b'TWIN reply kind status wanted string'),
]
CONTROLS = [(UNIT, b'PASS HASH-PROJECTIONS-UNIT cases=36'),
            (probe('keys'), b'PASS HASH-PROJECTIONS-PROBE entry=keys cases=13'),
            (probe('vals'), b'PASS HASH-PROJECTIONS-PROBE entry=vals cases=13'),
            (probe('keysBranch'), b'PASS HASH-PROJECTIONS-PROBE entry=keysBranch cases=1'),
            (probe('valsBranch'), b'PASS HASH-PROJECTIONS-PROBE entry=valsBranch cases=1'),
            (probe('valsHead'), b'PASS HASH-PROJECTIONS-PROBE entry=valsHead cases=3')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-hash-projections-mutants-') as temporary:
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
        if survivors or killed != len(MUTANTS) or killed != 16 or restored != 6:
            raise AssertionError(f'Mutation inventory killed={killed} restored={restored} survivors={survivors}')
        print(f'PASS HASH-PROJECTIONS-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL HASH-PROJECTIONS-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
