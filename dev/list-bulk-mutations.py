#!/usr/bin/env python3
"""Require compiling List bulk mutants to fail at named semantic assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/list_bulk_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/list_bulk_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/list-bulk-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-ORDER', 'store/store.ml', b'List.rev_append rest (value :: orient side values)',
     b'List.append rest (value :: orient side values)', UNIT, b'FAIL LIST-BULK-UNIT store order, count and complete state'),
    ('STORE-DROP', 'store/store.ml', b'List.rev_append rest (value :: orient side values)',
     b'List.rev_append (List.filter (fun _ -> false) rest) (value :: orient side values)', UNIT, b'FAIL LIST-BULK-UNIT store order, count and complete state'),
    ('STORE-FIRST', 'store/store.ml', b'List.rev_append rest (value :: orient side values)',
     b'List.rev_append rest ((value ^ "lost") :: orient side values)', UNIT, b'FAIL LIST-BULK-UNIT store order, count and complete state'),
    ('STORE-EXPIRY', 'store/store.ml', b'Ok (string_of_int (List.length values), put key (List values) store)',
     b'Ok (string_of_int (List.length values), put key (List values) { store with deadlines = Keys.remove key store.deadlines })',
     UNIT, b'FAIL LIST-BULK-UNIT store order, count and complete state'),
    ('STORE-TYPE', 'store/store.ml', b'let push ?(xx = false) ?(rest = []) side key value store = let* values = list key store in',
     b'let push ?(xx = false) ?(rest = []) side key value store = let values = Result.value ~default:[] (list key store) in',
     UNIT, b'FAIL LIST-BULK-UNIT store wrong type'),
    ('INTERPRETER-DIRECTION', 'store/interp.ml', b'if tag = 53 || tag = 63 then Store.Left else Store.Right',
     b'if tag = 53 || tag = 63 then Store.Right else Store.Left', UNIT, b'FAIL LIST-BULK-UNIT interpreter order, count and complete state'),
    ('INTERPRETER-ARGS', 'store/interp.ml', b'Store.push ~xx:(tag >= 63) ~rest (if tag = 53',
     b'Store.push ~xx:(tag >= 63) ~rest:(List.filter (fun _ -> false) rest) (if tag = 53', UNIT, b'FAIL LIST-BULK-UNIT interpreter order, count and complete state'),
    ('INTERPRETER-STATE', 'store/interp.ml', b'integer (Store.push ~xx:(tag >= 63) ~rest (if tag = 53 || tag = 63 then Store.Left else Store.Right) key first store)',
     b'integer (Result.map (fun (count, _) -> count, Store.empty) (Store.push ~xx:(tag >= 63) ~rest (if tag = 53 || tag = 63 then Store.Left else Store.Right) key first store))',
     UNIT, b'FAIL LIST-BULK-UNIT interpreter order, count and complete state'),
    ('LUA-DIRECTION', 'print/lua.ml', b"[53]='LPUSH',[54]='RPUSH'",
     b"[53]='RPUSH',[54]='LPUSH'", probe('right'), b'TWIN list order mismatch'),
    ('LUA-LAST', 'print/lua.ml', b'args[#args+1] = text(vs[1]); got =',
     b"args[#args+1] = 'lost'; got =", probe('right'), b'TWIN list order mismatch'),
    ('LUA-HEADS', 'print/lua.ml', b'args[#args+1], vs = text(vs[1]), vs[2]',
     b"args[#args+1], vs = 'lost', vs[2]", probe('right'), b'TWIN list order mismatch'),
    ('LUA-ARGUMENT-ORDER', 'print/lua.ml', b'for i = #xs, 1, -1 do tail =',
     b'for i = 1, #xs do tail =', probe('right'), b'TWIN list order mismatch'),
    ('READONLY', 'print/flags.ml', b'&& tag <> 52', b'&& tag <> 52 && tag <> 53 && tag <> 54',
     probe('right'), b'LIST-BULK write classification'),
    ('TWIN-ARGS', 'dev/lua-store.lua', b'list_call(command, key, amount, value, ...)',
     b'list_call(command, key, amount, value)', probe('right'), b'TWIN list length mismatch'),
    ('TWIN-DIRECTION', 'dev/lua-store.lua', b"(command == 'LPUSH' or command == 'LPUSHX') and 1 or #items + 1, item",
     b"(command == 'RPUSH' or command == 'RPUSHX') and 1 or #items + 1, item", probe('right'), b'TWIN list order mismatch'),
    ('TWIN-DROP', 'dev/lua-store.lua', b'ipairs({value, extra, ...})',
     b'ipairs({value})', probe('right'), b'TWIN list length mismatch'),
]
CONTROLS = [(UNIT, b'PASS LIST-BULK-UNIT cases=40'),
            (probe('left'), b'PASS LIST-BULK-PROBE entry=left cases=5'),
            (probe('right'), b'PASS LIST-BULK-PROBE entry=right cases=5'),
            (probe('within'), b'PASS LIST-BULK-PROBE entry=within cases=1'),
            (probe('earlier'), b'PASS LIST-BULK-PROBE entry=earlier cases=1'),
            (probe('computed'), b'PASS LIST-BULK-PROBE entry=computed cases=1')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-list-bulk-mutants-') as temporary:
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
        restored = 0
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
            restored += 1
        if survivors or killed != len(MUTANTS) or killed != 16 or restored != 6:
            raise AssertionError(f'Mutation inventory killed={killed} restored={restored} survivors={survivors}')
        print(f'PASS LIST-BULK-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-BULK-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
