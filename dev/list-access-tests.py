#!/usr/bin/env python3
"""List access parity, typed refusals and complete state on local hosts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('list_access_support', ROOT / 'dev/lists-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, tet = support.run, support.require, support.tet
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
MIN, MAX = '-9223372036854775808', '9223372036854775807'
READONLY = {'atHead', 'atTail', 'atStart', 'atOutside', 'atMin', 'atMax'}
EXAMPLES = [('main', b'welcome:bob\n'), ('newest', b'retry:carol\n')]


def commands():
    base = f'Reply {TAG} (jobs b"mail")'
    index = lambda n: f'(int64 b"{n}")'
    reads = {name: f'lindex {base} {index(n)}' for name, n in
             [('atHead', '0'), ('atTail', '-1'), ('atStart', '-3'), ('atOutside', '3'), ('atMin', MIN), ('atMax', MAX)]}
    writes = {name: f'lset {base} {index(n)} b"x"' for name, n in
              [('replace', '1'), ('replaceTail', '-1'), ('replaceOutside', '3'), ('replaceMin', MIN)]}
    writes['replaceBinary'] = f'lset {base} {index("0")} {tet(support.BINARY)}'
    trims = {name: f'ltrim {base} {index(first)} {index(last)}' for name, first, last in
             [('trimMiddle', '1', '1'), ('trimTail', '-2', '-1'), ('trimAll', MIN, MAX),
              ('trimGone', MAX, MAX), ('trimBefore', '0', MIN), ('trimReverse', '2', '0')]}
    return reads | writes | trims


def cases():
    values = [b'a', b'b', b'c']
    rows = []
    for name, answer in [('atHead', b'a'), ('atTail', b'c'), ('atStart', b'a'),
                         ('atOutside', None), ('atMin', None), ('atMax', None)]:
        rows += [(name, values, answer or b'', values, 'null' if answer is None else 'bulk'),
                 (name, None, b'', None, 'null')]
    rows += [('atHead', [value], value, [value], 'bulk') for value in
             (b'', support.BINARY, support.TEXT, b'01')]
    for name, after in [('replace', [b'a', b'x', b'c']), ('replaceTail', [b'a', b'b', b'x']),
                        ('replaceOutside', None), ('replaceMin', None)]:
        rows += [(name, values, b'OK' if after else b'ERR index out of range', after or values,
                  'status' if after else 'bulk'),
                 (name, None, b'ERR no such key', None, 'bulk')]
    rows += [('replaceBinary', values, b'OK', [support.BINARY, b'b', b'c'], 'status'),
             ('replaceBinary', None, b'ERR no such key', None, 'bulk')]
    for name, after in [('trimMiddle', [b'b']), ('trimTail', [b'b', b'c']), ('trimAll', values),
                        ('trimGone', None), ('trimBefore', None), ('trimReverse', None)]:
        rows += [(name, values, b'OK', after, 'status'), (name, None, b'OK', None, 'status')]
    for initial in (b'wrong', {b'f': b'v'}, {b'm'}):
        rows += [(name, initial, WRONG, initial, 'bulk') for name in ('atHead', 'replace', 'trimTail')]
    rows += [('earlier', values, b'a', [b'b', b'c'], 'bulk'), ('branch', None, b'', None, 'null')]
    require(len(rows) == 49, f'LIST-ACCESS case inventory {len(rows)}')
    return rows


def source():
    declarations = ['module ListAccessCases', 'schema jobs : String -> Key List tag b"queue"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => bulk b | array rs => array rs']
    for name, command in commands().items():
        declarations += [f'def {name}Script : Script Reply {TAG} := do {{ '
                         f'r <- {command}; pure Reply {TAG} (expose r) }}',
                         f'def {name} : Client Reply := do {{ '
                         f'r <- inv Reply {TAG} {name}Script; done Reply r }}']
    declarations += [f'def earlier : Client Reply := do {{ r <- inv Reply {TAG} atHeadScript; '
                     f'_ <- inv Reply {TAG} trimTailScript; done Reply r }}',
        f'def choose : Reply -> Script Reply {TAG} := fun (r : Reply) =>',
        f'case r as x in Reply return Script Reply {TAG} with',
        f'| nil => pure Reply {TAG} nil | int n => trimTailScript',
        f'| bulk b => pure Reply {TAG} (bulk b) | status b => pure Reply {TAG} (status b)',
        f'| err b => pure Reply {TAG} (err b) | array rs => pure Reply {TAG} (array rs)',
        f'def branchScript : Script Reply {TAG} := do {{ r <- {commands()["atHead"]}; choose r }}',
        f'def branch : Client Reply := do {{ r <- inv Reply {TAG} branchScript; done Reply r }}']
    for i, (entry, initial, _expected, _after, _kind) in enumerate(cases()):
        if isinstance(initial, list):
            seeds = ' '.join(f'_ <- rpush Reply {TAG} (jobs b"mail") {tet(v)};' for v in initial)
            declarations += [f'def seed{i} : Script Reply {TAG} := do {{ {seeds} pure Reply {TAG} nil }}',
                             f'def case{i} : Client Reply := do {{ _ <- inv Reply {TAG} seed{i}; {entry} }}']
    return '\n'.join(declarations) + '\n'


def offline(work, outputs):
    stores = twins = 0
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        support.lua(work, outputs[entry], initial, expected, after, kind)
        twins += 1
        seed = (initial.decode() if isinstance(initial, bytes) else '@hash' if isinstance(initial, dict)
                else '@set' if isinstance(initial, set) else '@missing')
        rows = []
        code = support.checker.check(work, 'ListAccessCases.tet',
            command=[str(ROOT / '_build/default/dev/store_run.exe'), 'ListAccessCases.tet',
                     f'case{i}' if isinstance(initial, list) else entry, KEY, seed, '1000000'], receive=rows.append)
        want = 'REPLY null\n' if kind == 'null' else f'REPLY {kind}:{expected.hex()}\n'
        require(code == 0 and rows == [want.encode()], f'LIST-ACCESS store reply {i}: {rows!r}')
        stores += 1
    require((stores, twins) == (49, 49), 'LIST-ACCESS oracle counts')
    print(f'PASS LIST-ACCESS-ORACLES store={stores} luajit={twins}', flush=True)


def refusals(work):
    typed = [commands()[n] for n in ('atHead', 'replace', 'trimTail')]
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = [(cmd.replace(TAG, '(tag b"elsewhere")'), 'List', mismatch + b'(In SMu Tag [] (ACtor tag)')
               for cmd in typed]
    for schema, constructor in [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('Set', 'Set'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]:
        invalid += [(cmd, schema, mismatch + f'(In SMu RedisType [] (ACtor {constructor})'.encode()) for cmd in typed]
    signed = b'CHECK unbound: bytesCons is not a constructor of Signed64'
    octets = b'CHECK unbound: signed64Bytes is not a constructor of Bytes'
    invalid += [(commands()['atHead'].replace('(int64 b"0")', 'b"0"'), 'List', signed),
                (commands()['replace'].replace('(int64 b"1")', 'b"1"'), 'List', signed),
                (commands()['replace'].replace('b"x"', '(int64 b"1")'), 'List', octets),
                (commands()['trimTail'].replace('(int64 b"-2")', 'b"0"'), 'List', signed),
                (commands()['trimTail'].replace('(int64 b"-1")', 'b"0"'), 'List', signed)]
    for n in ('01', '-0', '+1', '9223372036854775808', '-9223372036854775809'):
        invalid.append((commands()['atHead'].replace('int64 b"0"', f'int64 b"{n}"'), 'List', b'INT64'))
    for i, (cmd, schema, diagnostic) in enumerate(invalid):
        path = work / 'Refused.tet'
        path.write_text(f'module Refused\nschema jobs : String -> Key {schema} tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ r <- {cmd}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        output = work / f'refused-{i}'
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr,
                f'LIST-ACCESS refusal {i}: {result.returncode} {result.stderr!r}')
        require(not output.exists(), f'LIST-ACCESS refusal published output {i}')
    require(len(invalid) == 28, 'LIST-ACCESS refusal inventory')
    print(f'PASS LIST-ACCESS-REFUSALS cases={len(invalid)} atomic_output={len(invalid)}', flush=True)


def live(work, outputs):
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        hosts = readonly = rejected = 0
        for entry, initial, expected, after, _kind in cases():
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                if isinstance(initial, (list, set)):
                    command = 'RPUSH' if isinstance(initial, list) else 'SADD'
                    for value in initial:
                        run(redis + ['EVAL', f"return redis.call('{command}',KEYS[1]," + support.literal(value) + ')', '1', KEY])
                elif isinstance(initial, dict):
                    for field, value in initial.items():
                        run(redis + ['HSET', KEY, field, value])
                elif initial is not None:
                    run(redis + ['-x', 'SET', KEY], data=initial)
                ro = entry in READONLY
                run(redis + ['ACL', 'SETUSER', 'default', '-eval' if ro else '+eval', '-evalsha' if ro else '+evalsha'])
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                try:
                    expected.decode('utf-8')
                    code, stdout = 0, expected + b'\n'
                except UnicodeDecodeError:
                    code, stdout = 4, b''
                require(run(args, env=env, code=code) == stdout, f'LIST-ACCESS {host} {entry} reply')
                rejected += int(code != 0)
                readonly += int(ro)
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                kind = (b'none' if after is None else b'list' if isinstance(after, list) else
                        b'hash' if isinstance(after, dict) else b'set' if isinstance(after, set) else b'string')
                require(run(redis + ['TYPE', KEY]) == kind + b'\n', f'LIST-ACCESS {host} {entry} key type')
                if isinstance(after, list):
                    require(run(redis + ['LLEN', KEY]) == str(len(after)).encode() + b'\n', 'LIST-ACCESS stored length')
                    for i, value in enumerate(after):
                        require(run(redis + ['LINDEX', KEY, str(i)]) == value + b'\n', 'LIST-ACCESS stored order')
                elif isinstance(after, dict):
                    require(run(redis + ['HLEN', KEY]) == b'1\n' and run(redis + ['HGET', KEY, 'f']) == b'v\n',
                            'LIST-ACCESS preserved hash')
                elif isinstance(after, set):
                    require(run(redis + ['SCARD', KEY]) == b'1\n' and run(redis + ['SISMEMBER', KEY, 'm']) == b'1\n',
                            'LIST-ACCESS preserved set')
                elif after is not None:
                    require(run(redis + ['GET', KEY]) == after + b'\n', 'LIST-ACCESS preserved string')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'LIST-ACCESS unrelated key')
                hosts += 1
        require((hosts, readonly, rejected) == (98, 38, 2), f'LIST-ACCESS host counts {hosts} {readonly} {rejected}')
        print(f'PASS LIST-ACCESS-E2E cases=49 hosts={hosts} readonly={readonly} utf8_refusals={rejected}', flush=True)
    execs = 0
    for entry, expected in EXAMPLES:
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/RecentJobs.tet', '--entry', entry, '--host', host]) == expected,
                    f'LIST-ACCESS example {entry} {host}')
            execs += 1
    require(execs == 6, 'LIST-ACCESS example count')
    print(f'PASS LIST-ACCESS-EXAMPLE exec={execs}', flush=True)


def emit(work, path, entry):
    output = work / entry
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'LIST-ACCESS canonical bodies')
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(body.startswith(b'#!lua flags=no-writes\n') == (script['entry'] in {n + 'Script' for n in READONLY}),
                'LIST-ACCESS write classification')
    return output


def probe(entry):
    require(entry in (*commands(), 'earlier', 'branch'), 'LIST-ACCESS unknown probe entry')
    rows = [row for row in cases() if row[0] == entry]
    require(bool(rows), 'LIST-ACCESS empty probe')
    with tempfile.TemporaryDirectory(prefix='tether-list-access-probe-') as temporary:
        work = Path(temporary)
        path = work / 'ListAccessCases.tet'
        path.write_text(source())
        output = emit(work, path, entry)
        for _entry, initial, expected, after, kind in rows:
            support.lua(work, output, initial, expected, after, kind)
    print(f'PASS LIST-ACCESS-PROBE entry={entry} cases={len(rows)}', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--probe':
        probe(sys.argv[2])
        return
    require(sys.argv[1:] in ([], ['--static'], ['--offline'], ['--artifacts']),
            'Usage: list-access-tests.py [--static|--offline|--artifacts|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-list-access-') as temporary:
        work = Path(temporary)
        path = work / 'ListAccessCases.tet'
        path.write_text(source())
        outputs = {}
        for entry in (*commands(), 'earlier', 'branch'):
            outputs[entry] = emit(work, path, entry)
        require(len(outputs) == 19, 'LIST-ACCESS artifact count')
        print(f'PASS LIST-ACCESS-ARTIFACTS pairs={len(outputs)}', flush=True)
        if '--artifacts' not in sys.argv:
            refusals(work)
            for entry, expected in EXAMPLES:
                require(run(['./tether', 'run', 'examples/RecentJobs.tet', '--entry', entry]) == expected, 'LIST-ACCESS example')
            if '--static' not in sys.argv:
                offline(work, outputs)
            if not sys.argv[1:]:
                live(work, outputs)
    mode = f" mode={sys.argv[1].lstrip('-')}" if sys.argv[1:] else ''
    print(f'PASS LIST-ACCESS-TESTS{mode}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-ACCESS-TESTS {error}', file=sys.stderr)
        sys.exit(1)
