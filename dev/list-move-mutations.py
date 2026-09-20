#!/usr/bin/env python3
"""Require compiling LMOVE mutants to fail their intended semantic assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/list_move_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/list_move_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/list-move-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-FROM', 'store/store.ml', b'let lmove from_side to_side key other store = let* values',
     b'let lmove from_side to_side key other store = let from_side = (match from_side with Left -> Right | Right -> Left) in let* values',
     UNIT, b'FAIL LIST-MOVE-UNIT store reply and complete state'),
    ('STORE-TO', 'store/store.ml', b'let lmove from_side to_side key other store = let* values',
     b'let lmove from_side to_side key other store = let to_side = (match to_side with Left -> Right | Right -> Left) in let* values',
     UNIT, b'FAIL LIST-MOVE-UNIT store reply and complete state'),
    ('STORE-DESTINATION', 'store/store.ml', b'if key = other then remaining else destination',
     b'if key = other then remaining else destination @ destination', UNIT, b'FAIL LIST-MOVE-UNIT store reply and complete state'),
    ('STORE-CLEANUP', 'store/store.ml', b'~empty:(remaining = []) store', b'~empty:false store',
     UNIT, b'FAIL LIST-MOVE-UNIT store reply and complete state'),
    ('STORE-ALIAS-EXPIRY', 'store/store.ml', b'if key = other then store else save key (List remaining)',
     b'if key = other then remove key store else save key (List remaining)', UNIT, b'FAIL LIST-MOVE-UNIT store reply and complete state'),
    ('STORE-DESTINATION-EXPIRY', 'store/store.ml',
     b'put other (List moved) (if key = other then store else save key (List remaining) ~empty:(remaining = []) store)',
     b'put other (List moved) (remove other (if key = other then store else save key (List remaining) ~empty:(remaining = []) store))',
     UNIT, b'FAIL LIST-MOVE-UNIT store reply and complete state'),
    ('STORE-ATOMIC-ERROR', 'store/store.ml', b'let* destination = list other store in let remaining',
     b'let destination = Result.value ~default:[] (list other store) in let remaining', UNIT, b'FAIL LIST-MOVE-UNIT store wrong type'),
    ('STORE-MISSING', 'store/store.ml', b'orient from_side values with [] -> Ok (None, store)',
     b'orient from_side values with [] -> Ok (Some "", store)', UNIT, b'FAIL LIST-MOVE-UNIT store reply and complete state'),
    ('INTERP-END', 'store/interp.ml', b'[0, Store.Left; 1, Store.Right]', b'[0, Store.Right; 1, Store.Left]',
     UNIT, b'FAIL LIST-MOVE-UNIT interpreter reply and complete state'),
    ('INTERP-ORDER', 'store/interp.ml', b'Store.lmove from_side to_side key other store',
     b'Store.lmove to_side from_side key other store', UNIT, b'FAIL LIST-MOVE-UNIT interpreter reply and complete state'),
    ('LUA-FROM', 'print/lua.ml', b"s[3].tag == 0 and 'LEFT' or 'RIGHT'", b"s[3].tag == 0 and 'RIGHT' or 'LEFT'",
     probe('moveLR'), b'TWIN list order mismatch'),
    ('LUA-DESTINATION', 'print/lua.ml', b"'LMOVE',k,key(s[2])", b"'LMOVE',k,k",
     probe('moveLR'), b'TWIN list length mismatch'),
    ('WRITE-FLAG', 'print/flags.ml', b'&& tag <> 60', b'&& tag <> 60 && tag <> 68',
     probe('moveLR'), b'LIST-MOVE write classification'),
    ('TWIN-FROM', 'dev/lua-store.lua', b"table.remove(items, value == 'LEFT' and 1 or #items)",
     b"table.remove(items, value == 'LEFT' and #items or 1)", probe('moveLR'), b'TWIN list order mismatch'),
]
CONTROLS = [(UNIT, b'PASS LIST-MOVE-UNIT cases=104')] + [
    (probe(entry), ('PASS LIST-MOVE-PROBE ' + entry).encode()) for entry in ('moveLR', 'moveRL', 'sameLR', 'nilRetained')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=180)
    if result.returncode != code or (marker is not None and marker not in result.stdout + result.stderr):
        raise AssertionError(f'{args}: exit={result.returncode}, expected={code}, marker={marker!r}, '
                             f'output={(result.stdout + result.stderr)[-3000:]!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-list-move-mutants-') as temporary:
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
            require_anchor = original.count(old)
            if require_anchor != 1:
                raise AssertionError(f'Mutation anchor {name}: {require_anchor}')
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
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
        if survivors or killed != 14 or len(CONTROLS) != 5:
            raise AssertionError(f'Mutation inventory killed={killed} survivors={survivors}')
        print('PASS LIST-MOVE-MUTATIONS killed=14 survived=0 restored=5', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print('FAIL LIST-MOVE-MUTATIONS ' + str(error), file=sys.stderr)
        raise SystemExit(1)
