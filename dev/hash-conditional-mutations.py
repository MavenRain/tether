#!/usr/bin/env python3
"""Require compiling mutants to fail at the intended Hash assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/hash_conditional_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/hash_conditional_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/hash-conditional-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-OVERWRITE', 'store/store.ml', b'if nx && List.exists', b'if false && nx && List.exists', UNIT,
     b'FAIL HASH-CONDITIONAL-UNIT conditional insert and complete state'),
    ('STORE-NOOP-COUNT', 'store/store.ml', b'then Ok ("0", store) else let updated', b'then Ok ("1", store) else let updated', UNIT,
     b'FAIL HASH-CONDITIONAL-UNIT conditional insert and complete state'),
    ('STORE-NOOP-EXPIRY', 'store/store.ml', b'then Ok ("0", store) else let updated',
     b'then Ok ("0", { store with deadlines = Keys.remove key store.deadlines }) else let updated', UNIT,
     b'FAIL HASH-CONDITIONAL-UNIT conditional insert and complete state'),
    ('STORE-LENGTH', 'store/store.ml', b'~some:String.length value', b'~some:(fun _ -> 1) value', UNIT,
     b'FAIL HASH-CONDITIONAL-UNIT byte length'),
    ('INTERPRETER-NX', 'store/interp.ml', b'~nx:(tag = 59)', b'~nx:(tag = 9)', UNIT,
     b'FAIL HASH-CONDITIONAL-UNIT interpreter conditional insert'),
    ('INTERPRETER-LENGTH', 'store/interp.ml', b'then Store.hexists else Store.hstrlen', b'then Store.hexists else Store.hexists', UNIT,
     b'FAIL HASH-CONDITIONAL-UNIT interpreter length and complete state'),
    ('LUA-OVERWRITE', 'print/lua.ml', b"s.tag == 59 and 'HSETNX' or 'HSET'", b"s.tag == 59 and 'HSET' or 'HSET'", probe('insert'),
     b'TWIN hash field mismatch'),
    ('LUA-LENGTH', 'print/lua.ml', b"s.tag == 60 and 'HSTRLEN'", b"s.tag == 60 and 'HEXISTS'", probe('length'),
     b'HASH-CONDITIONAL LuaJIT reply'),
    ('LUA-DISPATCH-BOUND', 'print/lua.ml', b'elseif s.tag >= 39 and s.tag <= 51 then', b'elseif s.tag >= 39 then',
     probe('length'), b'out-length/body-0.lua'),
    ('READONLY-LENGTH', 'print/flags.ml', b'&& tag <> 60', b'&& true', probe('length'),
     b'HASH-CONDITIONAL write classification'),
    ('READONLY-INSERT', 'print/flags.ml', b'&& tag <> 60', b'&& tag <> 60 && tag <> 59', probe('insert'),
     b'HASH-CONDITIONAL write classification'),
    ('TWIN-OVERWRITE', 'dev/lua-store.lua', b'if fields[field] ~= nil then return 0 end', b'if false then return 0 end', probe('insert'),
     b'TWIN hash field mismatch'),
    ('TWIN-LENGTH', 'dev/lua-store.lua', b'fields[field] and #fields[field] or 0', b'fields[field] and 1 or 0', probe('length'),
     b'HASH-CONDITIONAL LuaJIT reply'),
]
CONTROLS = [(UNIT, b'PASS HASH-CONDITIONAL-UNIT cases=32'),
            (probe('insert'), b'PASS HASH-CONDITIONAL-PROBE entry=insert cases=7'),
            (probe('length'), b'PASS HASH-CONDITIONAL-PROBE entry=length cases=9')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')
    return output


def main():
    require_inventory = len(MUTANTS) == 13 and len({name for name, *_ in MUTANTS}) == 13 and len(CONTROLS) == 3
    if not require_inventory:
        raise AssertionError('Mutation inventory')
    with tempfile.TemporaryDirectory(prefix='tether-hash-conditional-mutants-') as temporary:
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
        if survivors or killed != 13 or restored != 3:
            raise AssertionError(f'Mutation inventory killed={killed} restored={restored} survivors={survivors}')
        print(f'PASS HASH-CONDITIONAL-MUTATIONS killed={killed} survived=0 restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL HASH-CONDITIONAL-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
