#!/usr/bin/env python3
"""Require compiling Set bulk mutants to fail at named semantic assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/set_bulk_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/set_bulk_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/set-bulk-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-DUPLICATES', 'store/store.ml', b'abs (Members.cardinal next - Members.cardinal values)',
     b'List.length (member :: rest)', UNIT, b'FAIL SET-BULK-UNIT store count and complete state'),
    ('STORE-DROP', 'store/store.ml', b'(update member values) rest',
     b'(update member values) (List.filter (fun _ -> false) rest)', UNIT, b'FAIL SET-BULK-UNIT store count and complete state'),
    ('STORE-FIRST', 'store/store.ml', b'(update member values) rest',
     b'(update (member ^ "lost") values) rest', UNIT, b'FAIL SET-BULK-UNIT store count and complete state'),
    ('STORE-EXPIRY', 'store/store.ml', b'save_set key next store',
     b'save_set key next { store with deadlines = Keys.remove key store.deadlines }',
     UNIT, b'FAIL SET-BULK-UNIT store count and complete state'),
    ('STORE-EMPTY', 'store/store.ml', b'save_set key next store',
     b'put key (Set (Members.elements next)) store', UNIT, b'FAIL SET-BULK-UNIT store count and complete state'),
    ('STORE-TYPE', 'store/store.ml', b'let change_set ?(rest = []) update key member store = let* values = members key store in',
     b'let change_set ?(rest = []) update key member store = let values = Result.value ~default:Members.empty (members key store) in',
     UNIT, b'FAIL SET-BULK-UNIT store wrong type'),
    ('INTERPRETER-DIRECTION', 'store/interp.ml', b'if tag = 55 then Store.Members.add else Store.Members.remove',
     b'if tag = 55 then Store.Members.remove else Store.Members.add', UNIT, b'FAIL SET-BULK-UNIT interpreter count and complete state'),
    ('INTERPRETER-ARGS', 'store/interp.ml', b'Store.change_set ~rest (if tag = 55',
     b'Store.change_set ~rest:(List.filter (fun _ -> false) rest) (if tag = 55', UNIT, b'FAIL SET-BULK-UNIT interpreter count and complete state'),
    ('INTERPRETER-STATE', 'store/interp.ml', b'integer (Store.change_set ~rest (if tag = 55 then Store.Members.add else Store.Members.remove) key first store)',
     b'integer (Result.map (fun (count, _) -> count, Store.empty) (Store.change_set ~rest (if tag = 55 then Store.Members.add else Store.Members.remove) key first store))',
     UNIT, b'FAIL SET-BULK-UNIT interpreter count and complete state'),
    ('LUA-COMMAND', 'print/lua.ml', b"[55]='SADD',[56]='SREM'",
     b"[55]='SREM',[56]='SADD'", probe('add'), b'TWIN expected set'),
    ('LUA-LAST', 'print/lua.ml', b'args[#args+1] = text(vs[1]); got =',
     b"args[#args+1] = 'lost'; got =", probe('add'), b'TWIN missing member'),
    ('LUA-HEADS', 'print/lua.ml', b'args[#args+1], vs = text(vs[1]), vs[2]',
     b"args[#args+1], vs = 'lost', vs[2]", probe('add'), b'TWIN missing member'),
    ('READONLY', 'print/flags.ml', b'&& tag <> 52', b'&& tag <> 52 && tag <> 55 && tag <> 56',
     probe('add'), b'SET-BULK write classification'),
    ('TWIN-ARGS', 'dev/lua-store.lua', b'return set_call(command, key, amount, value, ...)',
     b'return set_call(command, key, amount)', probe('add'), b'TWIN missing member'),
    ('TWIN-ADD-COUNT', 'dev/lua-store.lua', b'if not members[item] then added = added + 1 end',
     b'added = added + 1', probe('add'), b'SET-BULK LuaJIT reply'),
    ('TWIN-REMOVE-COUNT', 'dev/lua-store.lua', b'if members[item] then removed = removed + 1 end',
     b'removed = removed + 1', probe('remove'), b'SET-BULK LuaJIT reply'),
]
CONTROLS = [(UNIT, b'PASS SET-BULK-UNIT cases=44'),
            (probe('add'), b'PASS SET-BULK-PROBE entry=add cases=7'),
            (probe('remove'), b'PASS SET-BULK-PROBE entry=remove cases=7'),
            (probe('within'), b'PASS SET-BULK-PROBE entry=within cases=1'),
            (probe('earlier'), b'PASS SET-BULK-PROBE entry=earlier cases=1'),
            (probe('computed'), b'PASS SET-BULK-PROBE entry=computed cases=1')]
EXPECTED_CONTROLS = {b'PASS SET-BULK-UNIT cases=44',
                     b'PASS SET-BULK-PROBE entry=add cases=7',
                     b'PASS SET-BULK-PROBE entry=remove cases=7',
                     b'PASS SET-BULK-PROBE entry=within cases=1',
                     b'PASS SET-BULK-PROBE entry=earlier cases=1',
                     b'PASS SET-BULK-PROBE entry=computed cases=1'}


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')
    return output


def main():
    with tempfile.TemporaryDirectory(prefix='tether-set-bulk-mutants-') as temporary:
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
        wanted = {marker for _, marker in CONTROLS}
        if len(CONTROLS) != 6 or wanted != EXPECTED_CONTROLS:
            raise AssertionError(f'Control inventory controls={len(CONTROLS)} markers={sorted(wanted)}')
        observed = {marker for test, marker in CONTROLS if marker in run(root, test)}
        restored = len(observed)
        if survivors or killed != len(MUTANTS) or killed != 16 or observed != EXPECTED_CONTROLS:
            raise AssertionError(f'Mutation inventory killed={killed} restored={restored} survivors={survivors}')
        print(f'PASS SET-BULK-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL SET-BULK-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
