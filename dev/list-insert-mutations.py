#!/usr/bin/env python3
"""Require compiling LINSERT mutants to fail at their intended assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/list_insert_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/list_insert_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/list-insert-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-SIDE', 'store/store.ml', b'Left -> value :: item :: rest | Right -> item :: value :: rest',
     b'Left -> item :: value :: rest | Right -> value :: item :: rest', UNIT,
     b'FAIL LIST-INSERT-UNIT store length, order and complete state'),
    ('STORE-PIVOT', 'store/store.ml', b'if item = pivot then', b'if item <> pivot then', UNIT,
     b'FAIL LIST-INSERT-UNIT store length, order and complete state'),
    ('STORE-PREFIX', 'store/store.ml', b'List.rev_append prefix (match side', b'List.append prefix (match side', UNIT,
     b'FAIL LIST-INSERT-UNIT store length, order and complete state'),
    ('STORE-COUNT', 'store/store.ml', b'fun after -> string_of_int (List.length after)',
     b'fun after -> string_of_int (List.length values)', UNIT,
     b'FAIL LIST-INSERT-UNIT store length, order and complete state'),
    ('STORE-MISSING', 'store/store.ml', b'if values = [] then "0" else "-1"', b'if values = [] then "-1" else "-1"', UNIT,
     b'FAIL LIST-INSERT-UNIT store length, order and complete state'),
    ('STORE-NO-PIVOT', 'store/store.ml', b'if values = [] then "0" else "-1"', b'if values = [] then "0" else "0"', UNIT,
     b'FAIL LIST-INSERT-UNIT store length, order and complete state'),
    ('STORE-EXPIRY', 'store/store.ml', b'put key (List after) store', b'put key (List after) (remove key store)', UNIT,
     b'FAIL LIST-INSERT-UNIT store length, order and complete state'),
    ('INTERP-SIDE', 'store/interp.ml', b'if tag = 66 then Store.Left else Store.Right',
     b'if tag = 66 then Store.Right else Store.Left', UNIT,
     b'FAIL LIST-INSERT-UNIT interpreter length, order and complete state'),
    ('LUA-SIDE', 'print/lua.ml', b"s.tag == 66 and 'BEFORE' or 'AFTER'", b"s.tag == 66 and 'AFTER' or 'BEFORE'", probe('before'),
     b'TWIN list order mismatch'),
    ('LUA-OPERANDS', 'print/lua.ml', b"'AFTER',text(s[2]),text(s[3])", b"'AFTER',text(s[3]),text(s[2])", probe('computedAfter'),
     b'TWIN list length mismatch'),
    ('WRITE-FLAG', 'print/flags.ml', b'&& tag <> 60', b'&& tag <> 60 && tag <> 66 && tag <> 67', probe('before'),
     b'LIST-INSERT write classification'),
    ('TWIN-SIDE', 'dev/lua-store.lua', b"value == 'BEFORE' and index or index + 1",
     b"value == 'BEFORE' and index + 1 or index", probe('after'), b'TWIN list order mismatch'),
    ('TWIN-MISSING', 'dev/lua-store.lua', b"if command == 'LINSERT' then\n    if #items == 0 then return 0 end",
     b"if command == 'LINSERT' then\n    if #items == 0 then return -1 end", probe('before'), b'LISTS LuaJIT reply'),
    ('TWIN-NO-PIVOT', 'dev/lua-store.lua', b"    return -1\n  end\n  if command == 'LREM'",
     b"    return 0\n  end\n  if command == 'LREM'", probe('before'), b'LISTS LuaJIT reply'),
]
CONTROLS = [(UNIT, b'PASS LIST-INSERT-UNIT cases=50')] + [
    (probe(entry), f'PASS LIST-INSERT-PROBE entry={entry}'.encode())
    for entry in ('before', 'after', 'binaryBefore', 'computedAfter')
]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')
    return output


def main():
    if len(MUTANTS) != 14 or len({name for name, *_ in MUTANTS}) != 14 or len(CONTROLS) != 5:
        raise AssertionError('Mutation inventory')
    with tempfile.TemporaryDirectory(prefix='tether-list-insert-mutants-') as temporary:
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
        if survivors or killed != 14 or restored != 5:
            raise AssertionError(f'Mutation inventory killed={killed} restored={restored} survivors={survivors}')
        print(f'PASS LIST-INSERT-MUTATIONS killed={killed} survived=0 restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-INSERT-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
