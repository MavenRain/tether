#!/usr/bin/env python3
"""Require compiling mutants to fail at the intended String byte assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/string_bytes_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/string_bytes_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/string-bytes-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-ORDER', 'store/store.ml', b'previous ^ suffix', b'suffix ^ previous', UNIT,
     b'FAIL STRING-BYTES-UNIT append order, value and expiry'),
    ('STORE-COUNT', 'store/store.ml', b'Ok (string_of_int (String.length value), put key (Str value) store)',
     b'Ok ("0", put key (Str value) store)', UNIT, b'FAIL STRING-BYTES-UNIT append order, value and expiry'),
    ('STORE-EMPTY-CREATION', 'store/store.ml', b'put key (Str value) store)\nlet add',
     b'(if suffix = "" then store else put key (Str value) store))\nlet add', UNIT,
     b'FAIL STRING-BYTES-UNIT append order, value and expiry'),
    ('STORE-EXPIRY', 'store/store.ml', b'put key (Str value) store)\nlet add',
     b'put key (Str value) (remove key store))\nlet add', UNIT,
     b'FAIL STRING-BYTES-UNIT append order, value and expiry'),
    ('STORE-LENGTH', 'store/store.ml', b'~some:String.length value)) (get key store)',
     b'~some:(fun _ -> 1) value)) (get key store)', UNIT, b'FAIL STRING-BYTES-UNIT byte length'),
    ('STORE-SIZE', 'store/store.ml', b'current > 536870912 - extra', b'current >= 536870912 - extra', UNIT,
     b'FAIL STRING-BYTES-UNIT size boundary'),
    ('STORE-SIZE-WIRING', 'store/store.ml',
     b'let* () = append_size (String.length previous) (String.length suffix) in let value', b'let value', UNIT,
     b'FAIL STRING-BYTES-UNIT size limit at the append call site'),
    ('INTERPRETER-APPEND', 'store/interp.ml', b'Store.append key s store', b'Ok (Store.set key s store)', UNIT,
     b'FAIL ERR value is not an integer or out of range'),
    ('INTERPRETER-APPEND-WRITE', 'store/interp.ml', b'Store.append key s store',
     b'Result.map (fun (n, _) -> n, store) (Store.append key s store)', UNIT,
     b'FAIL STRING-BYTES-UNIT append interpreter'),
    ('INTERPRETER-LENGTH', 'store/interp.ml', b'| _ -> Store.strlen', b'| _ -> fun k s -> Ok (Store.exists k s)', UNIT,
     b'FAIL STRING-BYTES-UNIT length reply and complete state'),
    ('LUA-APPEND', 'print/lua.ml', b"redis.pcall('APPEND',k,text(s[2]))", b"redis.pcall('SET',k,text(s[2]))",
     probe('extend'), b'TWIN reply kind status wanted string'),
    ('LUA-LENGTH', 'print/lua.ml', b"[72]='STRLEN'", b"[72]='EXISTS'", probe('length'),
     b'STRING-BYTES LuaJIT reply'),
    ('TWIN-ORDER', 'dev/lua-store.lua', b'values[key] = previous .. amount', b'values[key] = amount .. previous',
     probe('extend'), b'TWIN stored value mismatch'),
    ('READONLY-LENGTH', 'print/flags.ml', b'&& tag <> 72', b'&& true', probe('length'),
     b'STRING-BYTES write classification'),
    ('READONLY-APPEND', 'print/flags.ml', b'&& tag <> 72', b'&& tag <> 72 && tag <> 71', probe('extend'),
     b'STRING-BYTES write classification'),
]
CONTROLS = [(UNIT, b'PASS STRING-BYTES-UNIT cases=60'),
            (probe('extend'), b'PASS STRING-BYTES-PROBE entry=extend cases=9'),
            (probe('length'), b'PASS STRING-BYTES-PROBE entry=length cases=9')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')
    return output


def main():
    require_inventory = len(MUTANTS) == 15 and len({name for name, *_ in MUTANTS}) == 15 and len(CONTROLS) == 3
    if not require_inventory:
        raise AssertionError('Mutation inventory')
    with tempfile.TemporaryDirectory(prefix='tether-string-bytes-mutants-') as temporary:
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
        if survivors or killed != 15 or restored != 3:
            raise AssertionError(f'Mutation inventory killed={killed} restored={restored} survivors={survivors}')
        print(f'PASS STRING-BYTES-MUTATIONS killed={killed} survived=0 restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL STRING-BYTES-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
