#!/usr/bin/env python3
"""Require compiling Hash write mutants to fail at named semantic assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/hset_many_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/hset_many_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/hset-many-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-DUPLICATES', 'store/store.ml', b'Keys.cardinal updated - Keys.cardinal fields',
     b'List.length ((field, value) :: rest)', UNIT, b'FAIL HSET-MANY-UNIT store count and complete state'),
    ('STORE-TAIL', 'store/store.ml', b'(Keys.add field value fields) rest',
     b'(Keys.add field value fields) (List.filter (fun _ -> false) rest)', UNIT, b'FAIL HSET-MANY-UNIT store count and complete state'),
    ('STORE-FIRST', 'store/store.ml', b'(Keys.add field value fields) rest',
     b'(Keys.add (field ^ "lost") value fields) rest', UNIT, b'FAIL HSET-MANY-UNIT store count and complete state'),
    ('STORE-ORDER', 'store/store.ml', b'(Keys.add field value fields) rest',
     b'(Keys.add field value fields) (List.rev rest)', UNIT, b'FAIL HSET-MANY-UNIT store count and complete state'),
    ('STORE-EXPIRY', 'store/store.ml', b'save_hash key updated store',
     b'save_hash key updated { store with deadlines = Keys.remove key store.deadlines }', UNIT, b'FAIL HSET-MANY-UNIT store count and complete state'),
    ('STORE-TYPE', 'store/store.ml', b'let hset ?(rest = []) key field value store = let* fields = hash key store in',
     b'let hset ?(rest = []) key field value store = let fields = Result.value ~default:Keys.empty (hash key store) in', UNIT, b'FAIL HSET-MANY-UNIT store wrong type'),
    ('INTERPRETER-ARGS', 'store/interp.ml', b'Store.hset ~rest key f v store',
     b'Store.hset ~rest:(List.filter (fun _ -> false) rest) key f v store', UNIT, b'FAIL HSET-MANY-UNIT interpreter count and complete state'),
    ('INTERPRETER-PAIR', 'store/interp.ml', b'let* v = text v in Ok (f, v)',
     b'let* v = text v in Ok (v, f)', UNIT, b'FAIL HSET-MANY-UNIT interpreter count and complete state'),
    ('INTERPRETER-STATE', 'store/interp.ml', b'integer (Store.hset ~rest key f v store)',
     b'integer (Result.map (fun (count, _) -> count, Store.empty) (Store.hset ~rest key f v store))', UNIT, b'FAIL HSET-MANY-UNIT interpreter count and complete state'),
    ('LUA-COMMAND', 'print/lua.ml', b"got = redis.pcall('HSET',unpack(args))",
     b"got = redis.pcall('HDEL',unpack(args))", probe('write'), b'TWIN expected hash'),
    ('LUA-LAST', 'print/lua.ml', b'args[#args+1], args[#args+2] = text(ps[1]), text(ps[2]); got =',
     b"args[#args+1], args[#args+2] = text(ps[1]), 'lost'; got =", probe('write'), b'TWIN hash field mismatch'),
    ('LUA-HEADS', 'print/lua.ml', b'text(ps[1]), text(ps[2]), ps[3]',
     b'text(ps[2]), text(ps[1]), ps[3]', probe('computed'), b'TWIN hash field mismatch'),
    ('LUA-FLATTEN', 'print/lua.ml', b'collect (v :: f :: acc) tail',
     b'collect (f :: v :: acc) tail', probe('many'), b'TWIN hash field mismatch'),
    ('READONLY', 'print/flags.ml', b'&& tag <> 52', b'&& tag <> 52 && tag <> 58',
     probe('write'), b'HSET-MANY write classification'),
    ('TWIN-ARGS', 'dev/lua-store.lua', b'local items, count = {field, value, ...}, 0',
     b'local items, count = {field, value}, 0', probe('write'), b'TWIN hash field mismatch'),
    ('TWIN-COUNT', 'dev/lua-store.lua', b'if fields[items[i]] == nil then count = count + 1 end',
     b'count = count + 1', probe('write'), b'HSET-MANY LuaJIT reply'),
]
CONTROLS = [(UNIT, b'PASS HSET-MANY-UNIT cases=43'),
            (probe('write'), b'PASS HSET-MANY-PROBE entry=write cases=9'),
            (probe('within'), b'PASS HSET-MANY-PROBE entry=within cases=1'),
            (probe('earlier'), b'PASS HSET-MANY-PROBE entry=earlier cases=1'),
            (probe('computed'), b'PASS HSET-MANY-PROBE entry=computed cases=1'),
            (probe('many'), b'PASS HSET-MANY-PROBE entry=many cases=3')]
EXPECTED_CONTROLS = {b'PASS HSET-MANY-UNIT cases=43',
                     b'PASS HSET-MANY-PROBE entry=write cases=9',
                     b'PASS HSET-MANY-PROBE entry=within cases=1',
                     b'PASS HSET-MANY-PROBE entry=earlier cases=1',
                     b'PASS HSET-MANY-PROBE entry=computed cases=1',
                     b'PASS HSET-MANY-PROBE entry=many cases=3'}


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')
    return output


def main():
    with tempfile.TemporaryDirectory(prefix='tether-hset-many-mutants-') as temporary:
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
        print(f'PASS HSET-MANY-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL HSET-MANY-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
