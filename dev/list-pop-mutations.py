#!/usr/bin/env python3
"""Compile each mutant and require a semantic failure, then restore controls."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pop_mutation_support', ROOT / 'dev/list-move-mutations.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run = support.run
UNIT = ['_build/default/dev/list_pop_tests.exe']
BUILD = ['dune', 'build', '-j', '2', 'bin/tether.exe', 'dev/store_run.exe', 'dev/list_pop_tests.exe']


def probe(entry):
    return [sys.executable, '-P', 'dev/list-pop-tests.py', '--probe', entry]


MUTANTS = [
    ('store-direction', 'store/store.ml', b'take count [] (orient side values)', b'take count [] values', UNIT, b'LIST-POP-UNIT store reply and complete state'),
    ('store-count', 'store/store.ml', b'take (Int64.pred n) (v :: acc) rest', b'take (Int64.sub n 2L) (v :: acc) rest', UNIT, b'LIST-POP-UNIT store reply and complete state'),
    ('store-nil', 'store/store.ml', b'if values = [] then None else Some popped', b'if values = [] then Some [] else Some popped', UNIT, b'LIST-POP-UNIT store reply and complete state'),
    ('store-order', 'store/store.ml', b'None else Some popped', b'None else Some (List.rev popped)', UNIT, b'LIST-POP-UNIT store reply and complete state'),
    ('store-zero', 'store/store.ml', b'if count = 0L then store else save key (List (orient side rest))', b'if count = 0L then remove key store else save key (List (orient side rest))', UNIT, b'LIST-POP-UNIT store reply and complete state'),
    ('store-expiry', 'store/store.ml', b'~empty:(rest = []) store)\nlet position', b'~empty:(rest = []) (remove key store))\nlet position', UNIT, b'LIST-POP-UNIT store reply and complete state'),
    ('store-negative', 'store/store.ml', b'if count < 0L then Error Pop_range', b'if count < Int64.min_int then Error Pop_range', UNIT, b'LIST-POP-UNIT store validation'),
    ('interpreter-direction', 'store/interp.ml', b'if tag = 69 then Store.Left else Store.Right', b'if tag = 69 then Store.Right else Store.Left', UNIT, b'LIST-POP-UNIT interpreter reply and complete state'),
    ('lua-count', 'print/lua.ml', b'args[2], next = text(s[2][1]), s[3] end; got = redis.pcall((s.tag == 21', b"args[2], next = '1', s[3] end; got = redis.pcall((s.tag == 21", probe('leftTwo'), b'TWIN list length mismatch'),
    ('lua-direction', 'print/lua.ml', b"(s.tag == 21 or s.tag == 69) and 'LPOP' or 'RPOP'", b"(s.tag == 21 or s.tag == 70) and 'LPOP' or 'RPOP'", probe('rightTwo'), b'TWIN list order mismatch'),
    ('lua-sort', 'print/lua.ml', b'and s.tag < 69 then table.sort(order', b'and s.tag < 71 then table.sort(order', probe('leftTwo'), b'LIST-POP LuaJIT reply'),
    ('lua-nil', 'print/lua.ml', b'elseif got == false then r = {tag=0} else', b'elseif got == false then r = {tag=5,{tag=0}} else', probe('nilRetained'), b'LIST-POP LuaJIT reply'),
    ('twin-direction', 'dev/lua-store.lua', b"popped[#popped+1] = table.remove(items, command == 'LPOP' and 1 or #items)", b"popped[#popped+1] = table.remove(items, command == 'RPOP' and 1 or #items)", probe('rightTwo'), b'TWIN list order mismatch'),
]
CONTROLS = [(UNIT, b'PASS LIST-POP-UNIT cases=109')] + [
    (probe(entry), ('PASS LIST-POP-PROBE ' + entry).encode()) for entry in ('leftTwo', 'rightTwo', 'nilRetained')]


def main():
    with tempfile.TemporaryDirectory(prefix='tether-list-pop-mutants-') as temporary:
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
                raise AssertionError(f'Mutation anchor {name}: {original.count(old)}')
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
        for test, marker in CONTROLS:
            run(root, test, marker=marker)
        if survivors or killed != 13 or len(CONTROLS) != 4:
            raise AssertionError(f'Mutation inventory killed={killed} survivors={survivors}')
        print('PASS LIST-POP-MUTATIONS killed=13 survived=0 restored=4', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print('FAIL LIST-POP-MUTATIONS ' + str(error), file=sys.stderr)
        raise SystemExit(1)
