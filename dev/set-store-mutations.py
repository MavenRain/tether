#!/usr/bin/env python3
"""Require compiling mutants to fail their intended Set store assertions."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT = ['_build/default/dev/set_store_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/set_store_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/set-store-tests.py', '--probe', entry]


MUTANTS = [
    ('STORE-UNION', 'store/interp.ml', b'if tag = 35 then Store.Members.union', b'if tag = 35 then Store.Members.inter', UNIT, b'FAIL SET-STORE-UNIT left only'),
    ('STORE-INTER', 'store/interp.ml', b'if tag = 36 then Store.Members.inter', b'if tag = 36 then Store.Members.union', UNIT, b'FAIL SET-STORE-UNIT left only'),
    ('STORE-DIFF', 'store/interp.ml', b'else Store.Members.diff) key left right store', b'else Store.Members.union) key left right store', UNIT, b'FAIL SET-STORE-UNIT right only'),
    ('STORE-DESTINATION', 'store/store.ml', b'save destination (Set values)', b'save key (Set values)', UNIT, b'FAIL SET-STORE-UNIT missing'),
    ('STORE-EMPTY', 'store/store.ml', b'(Set values) ~empty:(values = [])', b'(Set values) ~empty:false', UNIT, b'FAIL SET-STORE-UNIT missing'),
    ('STORE-COUNT', 'store/store.ml', b'string_of_int (List.length values), save destination', b'"0", save destination', UNIT, b'FAIL SET-STORE-UNIT left only'),
    ('STORE-ALIAS', 'store/store.ml', b'let* values = scombine op key other store in', b'let* values = scombine op key other (Keys.remove destination store) in', UNIT, b'FAIL SET-STORE-UNIT left only'),
    ('STORE-SECOND-SOURCE', 'store/store.ml', b'let* right = members other store', b'let* right = members key store', UNIT, b'FAIL SET-STORE-UNIT right only'),
    ('LUA-UNION', 'print/lua.ml', b"[35]='SUNIONSTORE'", b"[35]='SINTERSTORE'", probe('union'), b'TWIN expected set'),
    ('LUA-INTER', 'print/lua.ml', b"[36]='SINTERSTORE'", b"[36]='SUNIONSTORE'", probe('inter'), b'TWIN stored value mismatch'),
    ('LUA-DIFF', 'print/lua.ml', b"[37]='SDIFFSTORE'", b"[37]='SUNIONSTORE'", probe('diff'), b'TWIN stored value mismatch'),
    ('LUA-DESTINATION', 'print/lua.ml', b'[s.tag],k,key(s[2]),', b'[s.tag],key(s[2]),key(s[2]),', probe('union'), b'TWIN stored value mismatch'),
    ('LUA-SECOND-SOURCE', 'print/lua.ml', b'or key(s[3])', b'or key(s[2])', probe('union'), b'TWIN expected set'),
    ('LUA-COUNT', 'print/lua.ml', b"string.format('%d',got)", b"string.format('%d',got+1)", probe('union'), b'SET-STORE LuaJIT reply'),
    ('LUA-REPLY-TAG', 'print/lua.ml', b"else r = {tag=1,{tag=0,bytes(string.format('%d',got))}} end", b"else r = {tag=2,bytes(string.format('%d',got))} end", probe('unionTyped'), b'SET-STORE LuaJIT reply'),
    ('UNION-READONLY', 'print/flags.ml', b'tag <> 0 && tag <> 2', b'tag <> 0 && tag <> 35 && tag <> 2', probe('union'), b'SET-STORE write classification'),
    ('INTER-READONLY', 'print/flags.ml', b'tag <> 0 && tag <> 2', b'tag <> 0 && tag <> 36 && tag <> 2', probe('inter'), b'SET-STORE write classification'),
    ('DIFF-READONLY', 'print/flags.ml', b'tag <> 0 && tag <> 2', b'tag <> 0 && tag <> 37 && tag <> 2', probe('diff'), b'SET-STORE write classification'),
]
CONTROLS = [(UNIT, b'PASS SET-STORE-UNIT cases=322'),
            (probe('union'), b'PASS SET-STORE-PROBE entry=union cases=26'),
            (probe('inter'), b'PASS SET-STORE-PROBE entry=inter cases=26'),
            (probe('diff'), b'PASS SET-STORE-PROBE entry=diff cases=26'),
            (probe('unionTyped'), b'PASS SET-STORE-PROBE entry=unionTyped cases=1'),
            (probe('unionEarlier'), b'PASS SET-STORE-PROBE entry=unionEarlier cases=1')]


def run(root, args, code=0, marker=None):
    result = subprocess.run(args, cwd=root, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{args}: exit={result.returncode} expected={code} marker={marker!r}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-set-store-mutants-') as temporary:
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
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
        if survivors or killed != len(MUTANTS) or killed != 18 or len(CONTROLS) != 6:
            raise AssertionError(f'Mutation inventory killed={killed} survivors={survivors}')
        print(f'PASS SET-STORE-MUTATIONS killed={killed} survived={len(survivors)} restored={len(CONTROLS)}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL SET-STORE-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
