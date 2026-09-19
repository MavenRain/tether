#!/usr/bin/env python3
"""Require compiling Hash deletion mutants to fail at named semantic assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/hdel_many_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/hdel_many_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/hdel-many-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-DUPLICATES', 'store/store.ml', b'Keys.cardinal fields - Keys.cardinal next',
     b'List.length (field :: rest)', UNIT, b'FAIL HDEL-MANY-UNIT store count and complete state'),
    ('STORE-TAIL', 'store/store.ml', b'(Keys.remove field fields) rest',
     b'(Keys.remove field fields) (List.filter (fun _ -> false) rest)', UNIT, b'FAIL HDEL-MANY-UNIT store count and complete state'),
    ('STORE-FIRST', 'store/store.ml', b'(Keys.remove field fields) rest',
     b'(Keys.remove (field ^ "lost") fields) rest', UNIT, b'FAIL HDEL-MANY-UNIT store count and complete state'),
    ('STORE-EXPIRY', 'store/store.ml', b'save_hash key next store',
     b'save_hash key next { store with deadlines = Keys.remove key store.deadlines }',
     UNIT, b'FAIL HDEL-MANY-UNIT store count and complete state'),
    ('STORE-EMPTY', 'store/store.ml', b'save_hash key next store',
     b'put key (Hash (Keys.bindings next)) store', UNIT, b'FAIL HDEL-MANY-UNIT store count and complete state'),
    ('STORE-TYPE', 'store/store.ml', b'let hdel ?(rest = []) key field store = let* fields = hash key store in',
     b'let hdel ?(rest = []) key field store = let fields = Result.value ~default:Keys.empty (hash key store) in',
     UNIT, b'FAIL HDEL-MANY-UNIT store wrong type'),
    ('INTERPRETER-ARGS', 'store/interp.ml', b'Store.hdel ~rest key first store',
     b'Store.hdel key first store', UNIT, b'FAIL HDEL-MANY-UNIT interpreter count and complete state'),
    ('INTERPRETER-STATE', 'store/interp.ml', b'integer (Store.hdel ~rest key first store)',
     b'integer (Result.map (fun (count, _) -> count, Store.empty) (Store.hdel ~rest key first store))',
     UNIT, b'FAIL HDEL-MANY-UNIT interpreter count and complete state'),
    ('LUA-COMMAND', 'print/lua.ml', b"[57]='HDEL'",
     b"[57]='HEXISTS'", probe('remove'), b'TWIN stored value mismatch'),
    ('LUA-LAST', 'print/lua.ml', b'args[#args+1] = text(vs[1]); got =',
     b"args[#args+1] = 'lost'; got =", probe('remove'), b'TWIN stored value mismatch'),
    ('LUA-HEADS', 'print/lua.ml', b'args[#args+1], vs = text(vs[1]), vs[2]',
     b"args[#args+1], vs = 'lost', vs[2]", probe('remove'), b'TWIN stored value mismatch'),
    ('READONLY', 'print/flags.ml', b'&& tag <> 52', b'&& tag <> 52 && tag <> 57',
     probe('remove'), b'HDEL-MANY write classification'),
    ('TWIN-ARGS', 'dev/lua-store.lua', b'for _, name in ipairs({field, value, ...}) do',
     b'for _, name in ipairs({field}) do', probe('remove'), b'TWIN stored value mismatch'),
    ('TWIN-COUNT', 'dev/lua-store.lua', b'if fields[name] ~= nil then fields[name], count = nil, count + 1 end',
     b'fields[name], count = nil, count + 1', probe('remove'), b'HDEL-MANY LuaJIT reply'),
]
CONTROLS = [(UNIT, b'PASS HDEL-MANY-UNIT cases=36'),
            (probe('remove'), b'PASS HDEL-MANY-PROBE entry=remove cases=8'),
            (probe('within'), b'PASS HDEL-MANY-PROBE entry=within cases=1'),
            (probe('earlier'), b'PASS HDEL-MANY-PROBE entry=earlier cases=1'),
            (probe('computed'), b'PASS HDEL-MANY-PROBE entry=computed cases=1')]
EXPECTED_CONTROLS = {b'PASS HDEL-MANY-UNIT cases=36',
                     b'PASS HDEL-MANY-PROBE entry=remove cases=8',
                     b'PASS HDEL-MANY-PROBE entry=within cases=1',
                     b'PASS HDEL-MANY-PROBE entry=earlier cases=1',
                     b'PASS HDEL-MANY-PROBE entry=computed cases=1'}


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')
    return output


def main():
    with tempfile.TemporaryDirectory(prefix='tether-hdel-many-mutants-') as temporary:
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
        if len(CONTROLS) != 5 or wanted != EXPECTED_CONTROLS:
            raise AssertionError(f'Control inventory controls={len(CONTROLS)} markers={sorted(wanted)}')
        observed = {marker for test, marker in CONTROLS if marker in run(root, test)}
        restored = len(observed)
        if survivors or killed != len(MUTANTS) or killed != 14 or observed != EXPECTED_CONTROLS:
            raise AssertionError(f'Mutation inventory killed={killed} restored={restored} survivors={survivors}')
        print(f'PASS HDEL-MANY-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL HDEL-MANY-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
