#!/usr/bin/env python3
"""Compile Set algebra mutants and require the intended assertion failure."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/set_algebra_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/set_algebra_tests.exe']
COMBINE = (b'Store.scombine (if tag = 32 then Store.Members.union else if tag = 33 then '
           b'Store.Members.inter else Store.Members.diff) key other store')


def probe(entry):
    return [sys.executable, '-P', 'dev/set-algebra-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-UNION', 'store/interp.ml', b'if tag = 32 then Store.Members.union', b'if tag = 32 then Store.Members.inter',
     UNIT, b'FAIL SET-ALGEBRA-UNIT left only'),
    ('STORE-INTER', 'store/interp.ml', b'if tag = 33 then Store.Members.inter', b'if tag = 33 then Store.Members.diff',
     UNIT, b'FAIL SET-ALGEBRA-UNIT left only'),
    ('STORE-DIFF', 'store/interp.ml', b'else Store.Members.diff', b'else Store.Members.union',
     UNIT, b'FAIL SET-ALGEBRA-UNIT right only'),
    ('STORE-SECOND-KEY', 'store/store.ml', b'members other store', b'members key store',
     UNIT, b'FAIL SET-ALGEBRA-UNIT right only'),
    ('STORE-ORDER', 'store/store.ml', b'Members.elements (op left right)', b'List.rev (Members.elements (op left right))',
     UNIT, b'FAIL SET-ALGEBRA-UNIT left only'),
    ('STORE-STATE', 'store/interp.ml', b'keep (' + COMBINE + b')', b'Result.map (fun ss -> ss, Store.empty) (' + COMBINE + b')',
     UNIT, b'FAIL SET-ALGEBRA-UNIT missing'),
    ('STORE-KEY-OPERAND', 'store/interp.ml', b'fun s -> KeyName s', b'fun s -> Octets s',
     UNIT, b'FAIL STORE-SCRIPT-COMMAND'),
    ('LUA-SECOND-KEY', 'print/lua.ml', b'args[2], next = key(s[2]), s[3]', b'args[2], next = key(s[1]), s[3]',
     probe('diff'), b'SET-ALGEBRA LuaJIT reply'),
    ('LUA-UNION', 'print/lua.ml', b"[32]='SUNION'", b"[32]='SINTER'", probe('union'), b'SET-ALGEBRA LuaJIT reply'),
    ('LUA-INTER', 'print/lua.ml', b"[33]='SINTER'", b"[33]='SUNION'", probe('inter'), b'SET-ALGEBRA LuaJIT reply'),
    ('LUA-DIFF', 'print/lua.ml', b"[34]='SDIFF'", b"[34]='SUNION'", probe('diff'), b'SET-ALGEBRA LuaJIT reply'),
    ('UNION-WRITE', 'print/flags.ml', b'&& tag <> 32', b'&& true', probe('union'), b'SET-ALGEBRA write classification'),
    ('INTER-WRITE', 'print/flags.ml', b'&& tag <> 33', b'&& true', probe('inter'), b'SET-ALGEBRA write classification'),
    ('DIFF-WRITE', 'print/flags.ml', b'&& tag <> 34', b'&& true', probe('diff'), b'SET-ALGEBRA write classification'),
    ('BRANCH-WRITE', 'print/flags.ml', b'&& tag <> 32', b'&& tag <> 7 && tag <> 32',
     probe('unionBranch'), b'SET-ALGEBRA write classification'),
    ('LUA-ORDER', 'print/lua.ml', b'return byte_less(got[a],got[b])', b'return byte_less(got[b],got[a])',
     probe('union'), b'SET-ALGEBRA LuaJIT reply'),
    ('LUA-BULK', 'print/lua.ml', b'{tag=2,bytes(got[i])}', b'{tag=3,bytes(got[i])}',
     probe('unionHead'), b'TWIN reply kind status wanted string'),
]
CONTROLS = [(UNIT, b'PASS SET-ALGEBRA-UNIT cases=106'),
            (probe('union'), b'PASS SET-ALGEBRA-PROBE entry=union cases=22'),
            (probe('inter'), b'PASS SET-ALGEBRA-PROBE entry=inter cases=22'),
            (probe('diff'), b'PASS SET-ALGEBRA-PROBE entry=diff cases=22'),
            (probe('unionBranch'), b'PASS SET-ALGEBRA-PROBE entry=unionBranch cases=1'),
            (probe('unionHead'), b'PASS SET-ALGEBRA-PROBE entry=unionHead cases=3')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-set-algebra-mutants-') as temporary:
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
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
        if survivors or killed != len(MUTANTS) or killed != 17 or len(CONTROLS) != 6:
            raise AssertionError(f'Mutation inventory killed={killed} survivors={survivors}')
        print(f'PASS SET-ALGEBRA-MUTATIONS killed={killed} survived={len(survivors)} restored={len(CONTROLS)}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL SET-ALGEBRA-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
