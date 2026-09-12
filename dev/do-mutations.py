#!/usr/bin/env python3
"""Prove the continuation tests reject faults in the actual expander."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DIFFERS = b'FAIL DO-SYNTAX continuation differs:'
ACCEPTED = b'FAIL DO-SYNTAX malformed do accepted:'
# Every row carries the marker the syntax suite actually prints for it.
MUTANTS = [
    ('REPLY-TYPE', b'T.Colon; T.Ident "Reply";', b'T.Colon; T.Ident "Nat";', DIFFERS),
    ('ACTION-ORDER', b'parens loc action @ parens loc continuation',
     b'parens loc continuation @ parens loc action', DIFFERS),
    ('LOST-TAIL', b'T.RParen; T.DArrow] @ parens loc body',
     b'T.RParen; T.DArrow] @ tokens loc [T.Ident "nil"]', DIFFERS),
    ('FINAL-SEMI',
     b'| Semi loc :: _rest -> error loc "only a reply bind may precede the final expression"',
     b'| Semi _ :: rest -> block start rest', ACCEPTED),
]


def run(root, command, code, marker=None):
    child = subprocess.run(command, cwd=root, capture_output=True, timeout=120)
    output = child.stdout + child.stderr
    if child.returncode != code or (marker is not None and marker not in output):
        raise AssertionError(f'{command}: exit={child.returncode}\n{output!r}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-do-mutants-') as temporary:
        root = Path(temporary) / 'tree'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '__pycache__'))
        source = root / 'surface/do_notation.ml'
        original = source.read_bytes()
        build = ['dune', 'build', 'dev/do_tests.exe']
        test = [str(root / '_build/default/dev/do_tests.exe')]
        run(root, build, 0)
        run(root, test, 0, b'PASS DO-SYNTAX')
        for name, old, new, marker in MUTANTS:
            if original.count(old) != 1:
                raise AssertionError('Mutation anchor ' + name)
            source.write_bytes(original.replace(old, new, 1))
            run(root, build, 0)
            run(root, test, 1, marker)
            print(f'KILLED {name} by DO-SYNTAX', flush=True)
        source.write_bytes(original)
        run(root, build, 0)
        run(root, test, 0, b'PASS DO-SYNTAX')
        print(f'PASS DO-MUTATIONS killed={len(MUTANTS)} survived=0 restored=1', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL DO-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
