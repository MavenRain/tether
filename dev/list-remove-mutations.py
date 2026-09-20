#!/usr/bin/env python3
"""Require compiling LREM mutants to fail at their intended semantic assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/list_remove_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/list_remove_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/list-remove-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-ZERO', 'store/store.ml', b'count = 0L ||', b'false ||', UNIT,
     b'FAIL LIST-REMOVE-UNIT store count, order and complete state'),
    ('STORE-DIRECTION', 'store/store.ml', b'if count < 0L then Right else Left', b'if count < 0L then Left else Right', UNIT,
     b'FAIL LIST-REMOVE-UNIT store count, order and complete state'),
    ('STORE-MATCH', 'store/store.ml', b'v = value && (count = 0L ||', b'v <> value && (count = 0L ||', UNIT,
     b'FAIL LIST-REMOVE-UNIT store count, order and complete state'),
    ('STORE-EMPTY', 'store/store.ml', b'~empty:(kept = [])', b'~empty:false', UNIT,
     b'FAIL LIST-REMOVE-UNIT store count, order and complete state'),
    ('STORE-EXPIRY', 'store/store.ml', b'~empty:(kept = []) store',
     b'~empty:(kept = []) { store with deadlines = Keys.remove key store.deadlines }', UNIT,
     b'FAIL LIST-REMOVE-UNIT store count, order and complete state'),
    ('STORE-PRECEDENCE', 'store/store.ml', b'let* count = integer count in if count = Int64.min_int then Error Remove_range else let* values = list key store in',
     b'let* values = list key store in let* count = integer count in if count = Int64.min_int then Error Remove_range else', UNIT, b'FAIL LIST-REMOVE-UNIT store error precedence'),
    ('STORE-MINIMUM', 'store/store.ml', b'if count = Int64.min_int then Error Remove_range',
     b'if false then Error Remove_range', UNIT, b'FAIL LIST-REMOVE-UNIT store error precedence'),
    ('INTERPRETER-TAG', 'store/interp.ml', b'| 65, [Signed count; Octets value]', b'| 66, [Signed count; Octets value]',
     UNIT, b'FAIL STORE-SCRIPT-COMMAND'),
    ('LUA-COUNT', 'print/lua.ml', b"redis.pcall('LREM',k,text(s[2][1]),text(s[3]))",
     b"redis.pcall('LREM',k,'0',text(s[3]))", probe('head'), b'TWIN list length mismatch'),
    ('LUA-VALUE', 'print/lua.ml', b"redis.pcall('LREM',k,text(s[2][1]),text(s[3]))",
     b"redis.pcall('LREM',k,text(s[2][1]),'z')", probe('head'), b'TWIN list length mismatch'),
    ('LUA-DIRECTION', 'print/lua.ml', b"redis.pcall('LREM',k,text(s[2][1]),text(s[3]))",
     b"redis.pcall('LREM',k,'-1',text(s[3]))", probe('head'), b'TWIN list order mismatch'),
    ('READONLY', 'print/flags.ml', b'&& tag <> 60', b'&& tag <> 60 && tag <> 65',
     probe('head'), b'LIST-REMOVE write classification'),
    ('TWIN-DIRECTION', 'dev/lua-store.lua', b'local index = backward and #items or 1', b'local index = backward and 1 or #items',
     probe('tail'), b'TWIN list order mismatch'),
    ('TWIN-ZERO', 'dev/lua-store.lua', b"(value == '0' or #digits > #length", b"(value == '-0' or #digits > #length",
     probe('all'), b'TWIN list length mismatch'),
]
CONTROLS = [(UNIT, b'PASS LIST-REMOVE-UNIT cases=135')] + [
    (probe(entry), f'PASS LIST-REMOVE-PROBE entry={entry} cases={count}'.encode())
    for entry, count in [('head', 7), ('tail', 7), ('all', 7), ('binary', 1)]
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
    with tempfile.TemporaryDirectory(prefix='tether-list-remove-mutants-') as temporary:
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
        print(f'PASS LIST-REMOVE-MUTATIONS killed={killed} survived=0 restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-REMOVE-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
