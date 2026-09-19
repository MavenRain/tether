#!/usr/bin/env python3
"""Require compiling mutants to fail at the intended conditional List assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/list_conditional_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/list_conditional_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/list-conditional-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-CREATE', 'store/store.ml', b'if xx && values = []', b'if false && xx && values = []', UNIT,
     b'FAIL LIST-CONDITIONAL-UNIT store order, count and complete state'),
    ('STORE-MISSING-COUNT', 'store/store.ml', b'if xx && values = [] then Ok ("0", store)',
     b'if xx && values = [] then Ok ("1", store)', UNIT, b'FAIL LIST-CONDITIONAL-UNIT store order, count and complete state'),
    ('STORE-EXPIRY', 'store/store.ml', b'put key (List values) store',
     b'put key (List values) { store with deadlines = Keys.remove key store.deadlines }', UNIT,
     b'FAIL LIST-CONDITIONAL-UNIT store order, count and complete state'),
    ('INTERPRETER-SINGLE-X', 'store/interp.ml', b'~xx:(tag >= 61)', b'~xx:false', UNIT,
     b'FAIL LIST-CONDITIONAL-UNIT interpreter order, count and complete state'),
    ('INTERPRETER-BULK-X', 'store/interp.ml', b'~xx:(tag >= 63)', b'~xx:false', UNIT,
     b'FAIL LIST-CONDITIONAL-UNIT interpreter order, count and complete state'),
    ('INTERPRETER-SINGLE-DIRECTION', 'store/interp.ml', b'tag = 19 || tag = 61', b'tag = 19 || tag = 62', UNIT,
     b'FAIL LIST-CONDITIONAL-UNIT interpreter order, count and complete state'),
    ('INTERPRETER-BULK-DIRECTION', 'store/interp.ml', b'tag = 53 || tag = 63', b'tag = 53 || tag = 64', UNIT,
     b'FAIL LIST-CONDITIONAL-UNIT interpreter order, count and complete state'),
    ('LUA-LEFT-X', 'print/lua.ml', b"[61]='LPUSHX'", b"[61]='LPUSH'", probe('left'), b'TWIN stored value mismatch'),
    ('LUA-RIGHT-X', 'print/lua.ml', b"[62]='RPUSHX'", b"[62]='RPUSH'", probe('right'), b'TWIN stored value mismatch'),
    ('LUA-BULK-LEFT-X', 'print/lua.ml', b"[63]='LPUSHX'", b"[63]='LPUSH'", probe('leftBulk'), b'TWIN stored value mismatch'),
    ('LUA-BULK-RIGHT-X', 'print/lua.ml', b"[64]='RPUSHX'", b"[64]='RPUSH'", probe('rightBulk'), b'TWIN stored value mismatch'),
    ('LUA-SINGLE-DIRECTION', 'print/lua.ml', b"[61]='LPUSHX',[62]='RPUSHX'", b"[61]='RPUSHX',[62]='LPUSHX'",
     probe('left'), b'TWIN list order mismatch'),
    ('LUA-BULK-DIRECTION', 'print/lua.ml', b"[63]='LPUSHX',[64]='RPUSHX'", b"[63]='RPUSHX',[64]='LPUSHX'",
     probe('leftBulk'), b'TWIN list order mismatch'),
    ('LUA-LAST', 'print/lua.ml', b'args[#args+1] = text(vs[1]); got =', b'got =',
     probe('leftBulk'), b'TWIN list length mismatch'),
    ('READONLY-SINGLE', 'print/flags.ml', b'&& tag <> 60', b'&& tag <> 60 && tag <> 61',
     probe('left'), b'LIST-CONDITIONAL write classification'),
    ('READONLY-BULK', 'print/flags.ml', b'&& tag <> 60', b'&& tag <> 60 && tag <> 63',
     probe('leftBulk'), b'LIST-CONDITIONAL write classification'),
    ('TWIN-CREATE', 'dev/lua-store.lua', b"and #items == 0 then return 0 end", b"and false then return 0 end",
     probe('left'), b'TWIN stored value mismatch'),
    ('TWIN-DIRECTION', 'dev/lua-store.lua', b"(command == 'LPUSH' or command == 'LPUSHX') and 1",
     b"(command == 'LPUSH' or command == 'RPUSHX') and 1", probe('left'), b'TWIN list order mismatch'),
]
CONTROLS = [(UNIT, b'PASS LIST-CONDITIONAL-UNIT cases=74')] + [
    (probe(entry), f'PASS LIST-CONDITIONAL-PROBE entry={entry} cases=6'.encode())
    for entry in ('left', 'right', 'leftBulk', 'rightBulk')
]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')
    return output


def main():
    require_inventory = len(MUTANTS) == 18 and len({name for name, *_ in MUTANTS}) == 18 and len(CONTROLS) == 5
    if not require_inventory:
        raise AssertionError('Mutation inventory')
    with tempfile.TemporaryDirectory(prefix='tether-list-conditional-mutants-') as temporary:
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
                    run(root, test, code=1, marker=marker)
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
        if survivors or killed != 18 or restored != 5:
            raise AssertionError(f'Mutation inventory killed={killed} restored={restored} survivors={survivors}')
        print(f'PASS LIST-CONDITIONAL-MUTATIONS killed={killed} survived=0 restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-CONDITIONAL-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
