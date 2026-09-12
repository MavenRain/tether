#!/usr/bin/env python3
"""Compile dispatch mutants in a disposable tree and require specific failing checks."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = [
    ('NODE-MODE', 'runtime/redis-host.mjs', b"? '_RO' : ''", b"? '' : ''", 'host', 'RO-NODE load once'),
    ('NODE-FALLBACK', 'runtime/redis-host.mjs', b"['EVAL' + suffix,", b"['EVAL',", 'host', 'RO-NODE load once'),
    ('SH-MODE', 'print/sh.ml', b'if a.no_writes then "\'_RO\' "', b'if a.no_writes then "\'\' "', 'shell', 'RO-SH fallback order'),
    ('REST-ALLOWLIST', 'runtime/rest-twin.mjs', b", 'EVAL_RO', 'EVALSHA_RO'", b'', 'host', 'RO-REST admits'),
]


def run(root, args, code=0, marker=None):
    child = subprocess.run(args, cwd=root, capture_output=True, timeout=180)
    output = (child.stdout + child.stderr).decode('utf-8', 'replace')
    if child.returncode != code or (marker is not None and re.search(marker, output) is None):
        raise AssertionError(f'{args}: exit={child.returncode}\n{output}')


def main():
    with tempfile.TemporaryDirectory(prefix='tether-ro-mutants-') as temporary:
        root = Path(temporary) / 'tree'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            '.git', '_build', '.gatework', '.kanon-exec', '.kanon-wait', '__pycache__'))
        build = ['dune', 'build', 'bin/tether.exe']
        tests = {'host': ['node', '--test', '--test-reporter=tap', 'dev/readonly-host-tests.mjs'],
                 'shell': [sys.executable, '-P', 'dev/readonly-tests.py', '--shell-only']}
        run(root, build)
        for args in tests.values():
            run(root, args)
        killed = 0
        for name, relative, old, new, test, marker in MUTANTS:
            source = root / relative
            original = source.read_bytes()
            if original.count(old) != 1:
                raise AssertionError('Mutation anchor ' + name)
            try:
                source.write_bytes(original.replace(old, new, 1))
                run(root, build)
                failure = ('not ok [0-9]+ - ' if test == 'host' else 'FAIL RO-TESTS ')
                run(root, tests[test], 1, failure + re.escape(marker))
                killed += 1
                print(f'KILLED {name} by {marker}', flush=True)
            finally:
                source.write_bytes(original)
        run(root, build)
        for args in tests.values():
            run(root, args)
        print(f'PASS RO-MUTATIONS killed={killed} survived=0 restored=2', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL RO-MUTATIONS {error}', file=sys.stderr)
        sys.exit(1)
