#!/usr/bin/env python3
"""Compile each mutant and require the intended transfer assertion to fail."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/set_move_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/set_move_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/set-move-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-DIRECTION', 'store/interp.ml', b'Store.smove key other member store', b'Store.smove other key member store', UNIT, b'FAIL SET-MOVE-UNIT interpreter'),
    ('STORE-MEMBER', 'store/interp.ml', b'Store.smove key other member store', b'Store.smove key other (member ^ "x") store', UNIT, b'FAIL SET-MOVE-UNIT interpreter'),
    ('STORE-MISSING-SOURCE', 'store/store.ml', b'if Keys.mem key store.values then members other store', b'if true then members other store', UNIT, b'FAIL SET-MOVE-UNIT missing source'),
    ('STORE-DESTINATION-TYPE', 'store/store.ml', b'if Keys.mem key store.values then members other store', b'if false then members other store', UNIT, b'FAIL SET-MOVE-UNIT wrong type'),
    ('STORE-NO-OP', 'store/store.ml', b'then Ok (present, store) else let* _, next', b'then Ok ("1", store) else let* _, next', UNIT, b'FAIL SET-MOVE-UNIT store'),
    ('STORE-ALIAS', 'store/store.ml', b'then Ok (present, store)', b'then Ok ((if key = other then "0" else present), store)', UNIT, b'FAIL SET-MOVE-UNIT store'),
    ('STORE-REMOVAL', 'store/store.ml', b'let* _, next = srem key member store', b'let* _, next = sadd key member store', UNIT, b'FAIL SET-MOVE-UNIT store'),
    ('STORE-EXISTING-MEMBER', 'store/store.ml', b'fun (_, after) -> "1", after', b'fun (count, after) -> count, after', UNIT, b'FAIL SET-MOVE-UNIT store'),
    ('LUA-COMMAND', 'print/lua.ml', b"[38]='SMOVE'", b"[38]='SADD'", probe('move'), b'TWIN stored value mismatch'),
    ('LUA-DIRECTION', 'print/lua.ml', b'[s.tag],k,key(s[2]),', b'[s.tag],key(s[2]),k,', probe('move'), b'TWIN stored value mismatch'),
    ('LUA-MEMBER', 'print/lua.ml', b's.tag == 38 and text(s[3])', b's.tag == 38 and text(s[2][1])', probe('move'), b'TWIN stored value mismatch'),
    ('LUA-REPLY-TAG', 'print/lua.ml', b"else r = {tag=1,{tag=0,bytes(string.format('%d',got))}} end", b"else r = {tag=2,bytes(string.format('%d',got))} end", probe('typed'), b'SET-MOVE LuaJIT reply'),
    ('WRITE-FLAG', 'print/flags.ml', b'tag <> 0 && tag <> 2', b'tag <> 38 && tag <> 0 && tag <> 2', probe('move'), b'SET-MOVE write classification'),
    ('TWIN-MISSING-SOURCE', 'dev/lua-store.lua', b'if source == nil then return 0 end', b'if source == nil then return 1 end', probe('move'), b'SET-MOVE LuaJIT reply'),
    ('TWIN-ALIAS', 'dev/lua-store.lua', b'if key == amount then return 1 end', b'if key == amount then return 0 end', probe('same'), b'SET-MOVE LuaJIT reply'),
]
CONTROLS = [(UNIT, b'PASS SET-MOVE-UNIT cases=304'),
            (probe('move'), b'PASS SET-MOVE-PROBE entry=move cases=49'),
            (probe('same'), b'PASS SET-MOVE-PROBE entry=same cases=7'),
            (probe('typed'), b'PASS SET-MOVE-PROBE entry=typed cases=1'),
            (probe('binary'), b'PASS SET-MOVE-PROBE entry=binary cases=1')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=120)
    if result.returncode != code or (marker is not None and marker not in result.stdout + result.stderr):
        raise AssertionError(f'{args}: exit={result.returncode}\n{result.stdout!r}\n{result.stderr!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-set-move-mutations-') as temporary:
        root = Path(temporary) / 'root'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '.kanonx', '.kanon-replies', '__pycache__'))
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
        if survivors or killed != len(MUTANTS) or killed != 15 or len(CONTROLS) != 5:
            raise AssertionError(f'Mutation inventory killed={killed} survivors={survivors}')
        print(f'PASS SET-MOVE-MUTATIONS killed={killed} survived={len(survivors)} restored={len(CONTROLS)}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL SET-MOVE-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
