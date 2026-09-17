#!/usr/bin/env python3
"""Require compiling HMGET mutants to fail at named semantic assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/hmget_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/hmget_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/hmget-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-ORDER', 'store/store.ml', b'(first :: rest)', b'(List.rev (first :: rest))',
     UNIT, b'FAIL HMGET-UNIT store preserves order, nils and duplicates'),
    ('STORE-DROP', 'store/store.ml', b'(first :: rest)', b'(List.filter (fun _ -> first = "") rest)',
     UNIT, b'FAIL HMGET-UNIT store preserves order, nils and duplicates'),
    ('STORE-DUPLICATES', 'store/store.ml', b'(first :: rest)', b'(List.sort_uniq String.compare (first :: rest))',
     UNIT, b'FAIL HMGET-UNIT store preserves order, nils and duplicates'),
    ('STORE-NIL', 'store/store.ml', b'fun field -> Keys.find_opt field fields',
     b'fun field -> Some (Option.value ~default:"" (Keys.find_opt field fields))',
     UNIT, b'FAIL HMGET-UNIT store preserves order, nils and duplicates'),
    ('STORE-TYPE', 'store/store.ml', b'let hmget key first rest store = let* fields = hash key store in',
     b'let hmget key first rest store = let fields = Result.value ~default:Keys.empty (hash key store) in',
     UNIT, b'FAIL HMGET-UNIT store wrong type'),
    ('INTERPRETER-ARGS', 'store/interp.ml', b'Ok (b, first :: rest)', b'Ok (first, b :: rest)',
     UNIT, b'FAIL HMGET-UNIT interpreter reply and complete state'),
    ('INTERPRETER-STATE', 'store/interp.ml', b'keep (Store.hmget key first rest store)',
     b'Result.map (fun values -> values, Store.empty) (Store.hmget key first rest store)',
     UNIT, b'FAIL HMGET-UNIT interpreter reply and complete state'),
    ('INTERPRETER-NIL', 'store/interp.ml', b'array nullable (keep (Store.hmget',
     b'array (fun value -> nullable (Some (Option.value ~default:"" value))) (keep (Store.hmget',
     UNIT, b'FAIL HMGET-UNIT interpreter reply and complete state'),
    ('READONLY', 'print/flags.ml', b'&& tag <> 52', b'&& true',
     probe('lookup'), b'HMGET write classification'),
    ('LUA-ORDER', 'print/lua.ml', b'for n = #order, 1, -1 do', b'for n = 1, #order do',
     probe('lookup'), b'LISTS LuaJIT reply'),
    ('LUA-ARGUMENT-ORDER', 'print/lua.ml', b'for i = #xs, 1, -1 do tail =', b'for i = 1, #xs do tail =',
     probe('lookup'), b'LISTS LuaJIT reply'),
    ('LUA-NIL', 'print/lua.ml', b'got[i] == false and {tag=0}', b"got[i] == false and {tag=2,bytes('')}",
     probe('lookup'), b'LISTS LuaJIT reply'),
    ('LUA-LAST-FIELD', 'print/lua.ml', b'args[#args+1] = text(fs[1]); got =', b"args[#args+1] = 'absent'; got =",
     probe('one'), b'LISTS LuaJIT reply'),
    ('LUA-ARRAY', 'print/lua.ml', b'r = {tag=5,rs}', b'r = {tag=0,rs}',
     probe('lookup'), b'TWIN reply kind nil wanted array'),
    ('TWIN-ARGS', 'dev/lua-store.lua', b'hash_call(command, key, amount, value, ...)',
     b'hash_call(command, key, amount, value)', probe('lookup'), b'LISTS LuaJIT reply'),
    ('TWIN-NIL', 'dev/lua-store.lua', b'out[i] = fields[name] or false', b"out[i] = fields[name] or ''",
     probe('lookup'), b'LISTS LuaJIT reply'),
]
CONTROLS = [(UNIT, b'PASS HMGET-UNIT cases=26'),
            (probe('lookup'), b'PASS HMGET-PROBE entry=lookup cases=6'),
            (probe('one'), b'PASS HMGET-PROBE entry=one cases=3'),
            (probe('within'), b'PASS HMGET-PROBE entry=within cases=1'),
            (probe('earlier'), b'PASS HMGET-PROBE entry=earlier cases=1'),
            (probe('computed'), b'PASS HMGET-PROBE entry=computed cases=1')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-hmget-mutants-') as temporary:
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
        print(f'PASS HMGET-MUTATIONS killed={killed} survived={len(survivors)} restored={restored}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL HMGET-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
