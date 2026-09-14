#!/usr/bin/env python3
"""LRANGE array parity, typed refusals and complete state on local hosts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('list_range_support', ROOT / 'dev/lists-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, tet = support.run, support.require, support.tet
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
MIN, MAX = '-9223372036854775808', '9223372036854775807'
RANGES = [
    ('all', '0', '-1', [b'a', b'b', b'c']), ('middle', '1', '1', [b'b']),
    ('tail', '-2', '-1', [b'b', b'c']), ('boundary', '-3', '-1', [b'a', b'b', b'c']),
    ('clampStart', '-4', '-1', [b'a', b'b', b'c']), ('atHead', '0', '0', [b'a']),
    ('before', '0', '-4', []), ('clampStop', '0', '99', [b'a', b'b', b'c']),
    ('outside', '3', '99', []), ('reversed', '2', '0', []),
    ('extremes', MIN, MAX, [b'a', b'b', b'c']), ('minStop', MIN, MIN, []),
    ('maxStart', MAX, MAX, []), ('last', '-1', MAX, [b'c']),
]
READONLY = {name + 'Script' for name, *_ in RANGES} | {'headScript', 'rawScript'}
EXAMPLE = b'["welcome:alice","welcome:bob"]\n'


def command(first='0', last='-1'):
    return f'lrange Reply {TAG} (jobs b"mail") (int64 b"{first}") (int64 b"{last}")'


def cases():
    values = [b'a', b'b', b'c']
    rows = []
    for name, _first, _last, expected in RANGES:
        rows += [(name, values, expected, values, 'array'), (name, None, [], None, 'array')]
    for items in ([b'', support.TEXT, b'01', b'"\\\t\n\x7f'], [b'a', support.BINARY, b'c'],
                  [b'same', b'same'], [str(i).encode() for i in range(129)]):
        rows.append(('all', items, items, items, 'array'))
    rows += [('all', initial, WRONG, initial, 'status') for initial in (b'wrong', {b'f': b'v'}, {b'm'})]
    rows += [('head', values, b'a', values, 'bulk'), ('head', [b''], b'', [b''], 'bulk'),
             ('head', None, None, None, 'null'), ('earlier', values, values, [b'c'], 'array'),
             ('branch', values, values, values, 'array')]
    require(len(rows) == 40, 'LIST-RANGE case inventory')
    return rows


def source():
    declarations = ['module ListRangeCases', 'schema jobs : String -> Key List tag b"queue"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        'def first : Replies -> Reply := fun (rs : Replies) => case rs as x in Replies return Reply with',
        '| repliesNil => nil | repliesCons r rest => r',
        'def headReply : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => first rs']
    scripts = {name: (command(first, last), 'expose r') for name, first, last, _ in RANGES}
    scripts |= {'head': (command(), 'headReply r'), 'raw': (command(), 'r')}
    for name, (cmd, result) in scripts.items():
        declarations += [f'def {name}Script : Script Reply {TAG} := do {{ r <- {cmd}; pure Reply {TAG} ({result}) }}',
            f'def {name} : Client Reply := do {{ r <- inv Reply {TAG} {name}Script; done Reply r }}']
    declarations += [f'def trimScript : Script Reply {TAG} := do {{ '
        f'r <- ltrim Reply {TAG} (jobs b"mail") (int64 b"-1") (int64 b"-1"); pure Reply {TAG} r }}',
        f'def earlier : Client Reply := do {{ r <- inv Reply {TAG} allScript; '
        f'_ <- inv Reply {TAG} trimScript; done Reply r }}',
        f'def choose : Reply -> Script Reply {TAG} := fun (r : Reply) =>',
        f'case r as x in Reply return Script Reply {TAG} with',
        f'| nil => pure Reply {TAG} nil | int n => trimScript',
        f'| bulk b => pure Reply {TAG} (bulk b) | status b => pure Reply {TAG} (status b)',
        f'| err b => pure Reply {TAG} (err b) | array rs => pure Reply {TAG} (array rs)',
        f'def branchScript : Script Reply {TAG} := do {{ r <- {command()}; choose r }}',
        f'def branch : Client Reply := do {{ r <- inv Reply {TAG} branchScript; done Reply r }}']
    for i, (entry, initial, _expected, _after, _kind) in enumerate(cases()):
        if isinstance(initial, list):
            seeds = ' '.join(f'_ <- rpush Reply {TAG} (jobs b"mail") {tet(v)};' for v in initial)
            declarations += [f'def seed{i} : Script Reply {TAG} := do {{ {seeds} pure Reply {TAG} nil }}',
                f'def case{i} : Client Reply := do {{ _ <- inv Reply {TAG} seed{i}; {entry} }}']
    return '\n'.join(declarations) + '\n'


def wire(expected, kind):
    if kind == 'array':
        return ('array:[' + ','.join('bulk:' + v.hex() for v in expected) + ']').encode()
    return expected or b''


def offline(work, outputs):
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        support.lua(work, outputs[entry], initial, wire(expected, kind), after, kind)
        seed = (initial.decode() if isinstance(initial, bytes) else '@hash' if isinstance(initial, dict)
                else '@set' if isinstance(initial, set) else '@missing')
        rows = []
        code = support.checker.check(work, 'ListRangeCases.tet',
            command=[str(ROOT / '_build/default/dev/store_run.exe'), 'ListRangeCases.tet',
                     f'case{i}' if isinstance(initial, list) else entry, KEY, seed, '1000000'], receive=rows.append)
        encoded = (wire(expected, kind) if kind == 'array' else b'null' if kind == 'null'
                   else kind.encode() + b':' + expected.hex().encode())
        require(code == 0 and rows == [b'REPLY ' + encoded + b'\n'], f'LIST-RANGE store reply {i}: {rows!r}')
    print('PASS LIST-RANGE-ORACLES store=40 luajit=40', flush=True)


def refusals(work):
    cmd = command()
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = [(cmd.replace(TAG, '(tag b"elsewhere")'), 'List', mismatch + b'(In SMu Tag [] (ACtor tag)')]
    for schema, constructor in [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('Set', 'Set'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]:
        invalid.append((cmd, schema, mismatch + f'(In SMu RedisType [] (ACtor {constructor})'.encode()))
    for index in ('0', '-1'):
        invalid.append((cmd.replace(f'(int64 b"{index}")', f'b"{index}"'), 'List',
                        b'CHECK unbound: bytesCons is not a constructor of Signed64'))
        for bad in ('01', '-0', '+1', '9223372036854775808', '-9223372036854775809'):
            invalid.append((cmd.replace(f'int64 b"{index}"', f'int64 b"{bad}"'), 'List', b'INT64'))
    for i, (body, schema, diagnostic) in enumerate(invalid):
        path = work / 'Refused.tet'
        path.write_text(f'module Refused\nschema jobs : String -> Key {schema} tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ r <- {body}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        output = work / f'refused-{i}'
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'LIST-RANGE refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'LIST-RANGE refusal published output {i}')
    require(len(invalid) == 18, 'LIST-RANGE refusal inventory')
    print('PASS LIST-RANGE-REFUSALS cases=18 atomic_output=18', flush=True)


def driver_replies(work):
    nested = 'array (repliesCons (bulk b"outer") (repliesCons (array (repliesCons (bulk b"inner") repliesNil)) repliesNil))'
    replies = 0
    for term, expected in [('nil', b'\n'), ('bulk b"array:[bulk:61]\\n"', b'array:[bulk:61]\n\n'),
                           ('status b"OK"', b'OK\n'), ('array repliesNil', b'[]\n'),
                           (nested, b'["outer",["inner"]]\n')]:
        path = work / 'DriverReplies.tet'
        path.write_text(f'module DriverReplies\ndef s : Script Reply {TAG} := pure Reply {TAG} ({term})\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        require(run(['./tether', 'exec', str(path), '--host', 'luajit']) == expected, 'LIST-RANGE LuaJIT driver reply')
        replies += 1
    # The LuaJIT host answers a real LRANGE here, so the CLI reply encode and
    # decode path carries an empty array and a non-ASCII element. A binary
    # element has no UTF-8 text, so both legs refuse it with exit 4.
    for items, expected, code in [([], stdout([], 'array'), 0),
                                  ([support.TEXT], stdout([support.TEXT], 'array'), 0),
                                  ([support.BINARY], b'', 4)]:
        seeds = ''.join(f'_ <- rpush Reply {TAG} (jobs b"mail") {tet(value)}; ' for value in items)
        path = work / 'DriverRange.tet'
        path.write_text(f'module DriverRange\nschema jobs : String -> Key List tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ {seeds}r <- {command()}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        require(run(['./tether', 'exec', str(path), '--host', 'luajit'], code=code) == expected,
                'LIST-RANGE LuaJIT driver range reply')
        replies += 1
    print(f'PASS LIST-RANGE-DRIVER replies={replies}', flush=True)


def stdout(expected, kind):
    if kind == 'array':
        values = [v.decode('utf-8') for v in expected]
        return json.dumps(values, ensure_ascii=False, separators=(',', ':')).replace('\x7f', '\\u007f').encode() + b'\n'
    return (expected or b'') + b'\n'


def live(work, outputs):
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        seen = hosts = readonly = rejected = errors = 0
        for entry, initial, expected, after, kind in cases():
            seen += 1
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                if isinstance(initial, (list, set)):
                    operation = 'RPUSH' if isinstance(initial, list) else 'SADD'
                    for value in initial:
                        run(redis + ['EVAL', f"return redis.call('{operation}',KEYS[1]," + support.literal(value) + ')', '1', KEY])
                elif isinstance(initial, dict):
                    for field, value in initial.items():
                        run(redis + ['HSET', KEY, field, value])
                elif initial is not None:
                    run(redis + ['-x', 'SET', KEY], data=initial)
                ro = entry + 'Script' in READONLY
                run(redis + ['ACL', 'SETUSER', 'default', '-eval' if ro else '+eval', '-evalsha' if ro else '+evalsha'])
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                try:
                    wanted = stdout(expected, kind)
                    code = 0
                except UnicodeDecodeError:
                    code, wanted = 4, b''
                require(run(args, env=env, code=code) == wanted, f'LIST-RANGE {host} {entry} reply')
                rejected += int(code != 0)
                readonly += int(ro)
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                wanted_type = (b'none' if after is None else b'list' if isinstance(after, list) else
                               b'hash' if isinstance(after, dict) else b'set' if isinstance(after, set) else b'string')
                require(run(redis + ['TYPE', KEY]) == wanted_type + b'\n', 'LIST-RANGE key type')
                if isinstance(after, list):
                    require(run(redis + ['LLEN', KEY]) == str(len(after)).encode() + b'\n', 'LIST-RANGE stored length')
                    for i, value in enumerate(after):
                        require(run(redis + ['LINDEX', KEY, str(i)]) == value + b'\n', 'LIST-RANGE stored order')
                elif isinstance(after, dict):
                    require(run(redis + ['HLEN', KEY]) == b'1\n' and run(redis + ['HGET', KEY, 'f']) == b'v\n', 'LIST-RANGE preserved hash')
                elif isinstance(after, set):
                    require(run(redis + ['SCARD', KEY]) == b'1\n' and run(redis + ['SISMEMBER', KEY, 'm']) == b'1\n', 'LIST-RANGE preserved set')
                elif after is not None:
                    require(run(redis + ['GET', KEY]) == after + b'\n', 'LIST-RANGE preserved string')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'LIST-RANGE unrelated key')
                hosts += 1
        # The twin has no ZSet and no Stream kind, so the two remaining
        # wrong-type kinds reach the live hosts only.
        for seed, wanted_type in [(['ZADD', KEY, '1', 'm'], b'zset'), (['XADD', KEY, '*', 'f', 'v'], b'stream')]:
            seen += 1
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                run(redis + seed)
                run(redis + ['ACL', 'SETUSER', 'default', '-eval', '-evalsha'])
                output = outputs['all']
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                require(run(args, env=env) == stdout(WRONG, 'status'), f'LIST-RANGE {host} {wanted_type.decode()} reply')
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                require(run(redis + ['TYPE', KEY]) == wanted_type + b'\n', 'LIST-RANGE key type')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'LIST-RANGE unrelated key')
                hosts += 1
                readonly += 1
        run(redis + ['FLUSHDB'])
        run(redis + ['SET', KEY, 'wrong'])
        run(redis + ['ACL', 'SETUSER', 'default', '-eval', '-evalsha'])
        output = outputs['raw']
        for args in (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)],
                     ['/bin/bash', str(output / 'prog.sh')]):
            require(run(args, env=env, code=4) == b'', 'LIST-RANGE error stops host')
            require(run(redis + ['GET', KEY]) == b'wrong\n', 'LIST-RANGE error preserves key')
            hosts += 1
            readonly += 1
            errors += 1
        require((seen, hosts, readonly, rejected, errors) == (42, 86, 82, 2, 2),
                f'LIST-RANGE host counts {seen} {hosts} {readonly} {rejected} {errors}')
        print(f'PASS LIST-RANGE-E2E cases={seen} hosts={hosts} readonly={readonly} '
              f'utf8_refusals={rejected} errors={errors}', flush=True)
    for entry in ('main', 'retained'):
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/QueuePreview.tet', '--entry', entry, '--host', host]) == EXAMPLE,
                    f'LIST-RANGE example {entry} {host}')
    print('PASS LIST-RANGE-EXAMPLE exec=6', flush=True)


def emit(work, path, entry):
    output = work / entry
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'LIST-RANGE canonical bodies')
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(body.startswith(b'#!lua flags=no-writes\n') == (script['entry'] in READONLY), 'LIST-RANGE write classification')
    return output


def main():
    entries = [name for name, *_ in RANGES] + ['head', 'earlier', 'branch', 'raw']
    if len(sys.argv) == 3 and sys.argv[1] == '--probe':
        entry = sys.argv[2]
        rows = [row for row in cases() if row[0] == entry]
        require(bool(rows), 'LIST-RANGE unknown or empty probe')
        with tempfile.TemporaryDirectory(prefix='tether-list-range-probe-') as temporary:
            work = Path(temporary)
            path = work / 'ListRangeCases.tet'
            path.write_text(source())
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                support.lua(work, output, initial, wire(expected, kind), after, kind)
        print(f'PASS LIST-RANGE-PROBE entry={entry} cases={len(rows)}', flush=True)
        return
    require(sys.argv[1:] in ([], ['--static'], ['--offline'], ['--artifacts']),
            'Usage: list-range-tests.py [--static|--offline|--artifacts|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-list-range-') as temporary:
        work = Path(temporary)
        path = work / 'ListRangeCases.tet'
        path.write_text(source())
        outputs = {entry: emit(work, path, entry) for entry in entries}
        require(len(outputs) == 18, 'LIST-RANGE artifact count')
        print('PASS LIST-RANGE-ARTIFACTS pairs=18', flush=True)
        if '--artifacts' not in sys.argv:
            refusals(work)
            for entry in ('main', 'retained'):
                require(run(['./tether', 'run', 'examples/QueuePreview.tet', '--entry', entry]) == EXAMPLE, 'LIST-RANGE example')
            if '--static' not in sys.argv:
                offline(work, outputs)
                driver_replies(work)
            if not sys.argv[1:]:
                live(work, outputs)
    mode = f" mode={sys.argv[1].lstrip('-')}" if sys.argv[1:] else ''
    print(f'PASS LIST-RANGE-TESTS{mode}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-RANGE-TESTS {error}', file=sys.stderr)
        sys.exit(1)
