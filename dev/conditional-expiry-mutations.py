#!/usr/bin/env python3
"""Score conditional-expiry source defects against specific assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/conditional_expiry_tests.exe']
UNIT = ['_build/default/dev/conditional_expiry_tests.exe']


def probe(name):
    return [sys.executable, '-P', 'dev/conditional-expiry-tests.py', '--probe', name]


MUTANTS = [
    ('STORE-NX', 'store/store.ml', b'NX -> Option.is_none previous', b'NX -> Option.is_some previous', UNIT, b'FAIL CONDITIONAL-UNIT condition matrix reply'),
    ('STORE-XX', 'store/store.ml', b'XX -> Option.is_some previous', b'XX -> Option.is_none previous', UNIT, b'FAIL CONDITIONAL-UNIT condition matrix reply'),
    ('STORE-GT-EQUAL', 'store/store.ml', b'deadline > old', b'deadline >= old', UNIT, b'FAIL CONDITIONAL-UNIT condition matrix reply'),
    ('STORE-LT-EQUAL', 'store/store.ml', b'deadline < old', b'deadline <= old', UNIT, b'FAIL CONDITIONAL-UNIT condition matrix reply'),
    ('STORE-GT-INFINITY', 'store/store.ml', b'GT -> Option.fold ~none:false', b'GT -> Option.fold ~none:true', UNIT, b'FAIL CONDITIONAL-UNIT condition matrix reply'),
    ('STORE-LT-INFINITY', 'store/store.ml', b'LT -> Option.fold ~none:true', b'LT -> Option.fold ~none:false', UNIT, b'FAIL CONDITIONAL-UNIT condition matrix reply'),
    ('INTERPRETER-CONDITION', 'store/interp.ml', b'0, Store.NX', b'0, Store.XX', probe('expireIfpersistentNX'), b'TTL interpreter reply'),
    ('INTERPRETER-CLOCK', 'store/interp.ml', b'~absolute:(tag >= 50)', b'~absolute:false', probe('clock'), b'TTL interpreter reply'),
    ('LUA-NX', 'print/lua.ml', b"[0]='NX'", b"[0]='XX'", probe('expireIfpersistentNX'), b'TWIN expiry mismatch'),
    ('LUA-GT', 'print/lua.ml', b"[2]='GT'", b"[2]='LT'", probe('exactAdjacentGT'), b'TWIN expiry mismatch'),
    ('LUA-PAT', 'print/lua.ml', b"[51]='PEXPIREAT'", b"[51]='EXPIREAT'", probe('pexpireatIfhigherXX'), b'TWIN expiry mismatch'),
    ('TWIN-NX', 'dev/lua-store.lua', b"(value == 'NX' and old ~= nil)", b"(value == 'NX' and false)", probe('expireIfhigherNX'), b'TWIN expiry mismatch'),
    ('TWIN-PRECISION', 'dev/lua-store.lua', b'before(old, deadline)', b'tonumber(old) < tonumber(deadline)', probe('exactAdjacentGT'), b'TWIN expiry mismatch'),
] + [(f'WRITE-FLAG-{tag}', 'print/flags.ml', b'tag <> 0 && tag <> 2',
       f'tag <> {tag} && tag <> 0 && tag <> 2'.encode(), probe(name + 'missingNX'), b'TTL write classification')
      for tag, name in [(48, 'expireIf'), (49, 'pexpireIf'), (50, 'expireatIf'), (51, 'pexpireatIf')]]
CONTROLS = [(UNIT, b'PASS CONDITIONAL-UNIT cases=878')] + [
    (probe(name), ('PASS CONDITIONAL-PROBE ' + name).encode()) for name in
    ('clock', 'expireIfmissingNX', 'pexpireIfmissingNX', 'expireatIfmissingNX',
     'pexpireatIfmissingNX', 'expireIfpersistentNX', 'expireIfhigherNX',
     'exactAdjacentGT', 'pexpireatIfhigherXX')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=120)
    if result.returncode != code or marker is not None and marker not in result.stdout + result.stderr:
        raise AssertionError(f'{args}: exit={result.returncode}\n{result.stdout!r}\n{result.stderr!r}')


def main():
    if len(MUTANTS) != 17 or len(CONTROLS) != 10:
        raise AssertionError('Conditional expiry mutation inventory')
    with tempfile.TemporaryDirectory(prefix='tether-conditional-mutations-') as temporary:
        root = Path(temporary) / 'root'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '.kanonx', '.kanon-replies', '__pycache__'))
        run(root, BUILD)
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
        killed = 0
        for name, relative, old, new, test, marker in MUTANTS:
            path = root / relative
            original = path.read_bytes()
            if original.count(old) != 1:
                raise AssertionError('Mutation anchor ' + name)
            try:
                path.write_bytes(original.replace(old, new, 1))
                run(root, BUILD)
                run(root, test, code=1, marker=marker)
                killed += 1
                print(f'KILLED {name} by {marker.decode()}', flush=True)
            finally:
                path.write_bytes(original)
        run(root, BUILD)
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
        if killed != len(MUTANTS):
            raise AssertionError('Conditional expiry survivor')
        print(f'PASS CONDITIONAL-MUTATIONS killed={killed} survived=0 restored={len(CONTROLS)}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL CONDITIONAL-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
