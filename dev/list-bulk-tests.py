#!/usr/bin/env python3
"""Variadic List pushes across the independent store, twin and live Redis."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('list_bulk_support', ROOT / 'dev/lists-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, tet = support.run, support.require, support.tet
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
VALUES = [b'a', b'b', b'a', b'c', b'']
QUERY = {
    'left': ('lpushMany', VALUES), 'right': ('rpushMany', VALUES),
    'leftOne': ('lpushMany', [b'one']), 'rightOne': ('rpushMany', [b'one']),
    'leftMany': ('lpushMany', [f'v{i:03}'.encode() for i in range(129)]),
    'rightMany': ('rpushMany', [f'v{i:03}'.encode() for i in range(129)]),
    'binaryLeft': ('lpushMany', [bytes(range(256)), b'', support.BINARY]),
    'binaryRight': ('rpushMany', [bytes(range(256)), b'', support.BINARY]),
    'computed': ('rpushMany', VALUES), 'within': ('rpushMany', VALUES),
    'snapshot': ('rpushMany', VALUES), 'raw': ('lpushMany', VALUES),
}
ENTRIES = tuple(QUERY) + ('earlier',)
EXAMPLES = {
    'main': b'["welcome:alice","welcome:bob","welcome:carol"]\n',
    'priority': b'["retry:bob","retry:alice","welcome:alice","welcome:bob","welcome:carol"]\n',
    'retained': b'3\n',
}


def arguments(values):
    require(bool(values), 'LIST-BULK nonempty test arguments')
    result = f'(bulkOne {tet(values[-1])})'
    for value in reversed(values[:-1]):
        result = f'(bulkMore {tet(value)} {result})'
    return result


def command(name, values):
    return f'{name} Reply {TAG} (jobs b"mail") {arguments(values)}'


def cases():
    inputs = [
        ('left', None), ('left', [b'old', b'tail']),
        ('right', None), ('right', [b'old', b'tail']),
        ('leftOne', None), ('rightOne', [b'']),
        ('leftMany', [b'old']), ('rightMany', None),
        ('binaryLeft', None), ('binaryRight', [b'old']),
        ('computed', [b'old']), ('within', [b'old']), ('earlier', [b'old']),
        ('snapshot', None), ('snapshot', [support.TEXT, b'"\n$(touch forbidden)\\']),
        ('snapshot', [b'\xff']), ('raw', None),
    ]
    inputs += [(entry, initial) for entry in ('left', 'right')
               for initial in (b'wrong', {b'f': b'v'}, {b'm'})]
    rows = []
    for entry, initial in inputs:
        if initial is not None and not isinstance(initial, list):
            rows.append((entry, initial, WRONG, initial, 'status'))
            continue
        name, values = QUERY['right' if entry == 'earlier' else entry]
        after = (list(reversed(values)) + (initial or []) if name == 'lpushMany'
                 else (initial or []) + values)
        expected, kind = (after, 'array') if entry == 'snapshot' else (str(len(after)).encode(), 'int')
        rows.append((entry, initial, expected, None if entry in ('within', 'earlier') else after, kind))
    require(len(rows) == 23, 'LIST-BULK case inventory')
    return rows


def source(seed=None):
    declarations = ['module ListBulkCases', 'schema jobs : String -> Key List tag b"queue"',
        'def identity : Bytes -> Bytes := fun (b : Bytes) => b',
        'def keepArgs : BulkArgs -> BulkArgs := fun (args : BulkArgs) => args',
        'def prepend : Bytes -> BulkArgs -> BulkArgs := fun (b : Bytes) (rest : BulkArgs) => bulkMore b rest',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        f'def removeScript : Script Reply {TAG} := do {{ r <- del Reply List {TAG} (jobs b"mail"); pure Reply {TAG} r }}']
    for entry, (name, values) in QUERY.items():
        cmd = command(name, values)
        if entry == 'computed':
            cmd = cmd.replace(arguments(values),
                f'(prepend (identity {tet(values[0])}) (keepArgs {arguments(values[1:])}))')
        next_step = (f'_ <- del Reply List {TAG} (jobs b"mail"); ' if entry == 'within' else
            f'view <- lrange Reply {TAG} (jobs b"mail") (int64 b"0") (int64 b"-1"); '
            if entry == 'snapshot' else '')
        result = 'r' if entry == 'raw' else 'view' if entry == 'snapshot' else 'expose r'
        declarations += [f'def {entry}Script : Script Reply {TAG} := do {{ r <- {cmd}; '
            f'{next_step}pure Reply {TAG} ({result}) }}',
            f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; done Reply r }}']
    declarations += [f'def earlier : Client Reply := do {{ r <- inv Reply {TAG} rightScript; '
        f'_ <- inv Reply {TAG} removeScript; done Reply r }}']
    if seed is not None:
        entry, initial, *_ = cases()[seed]
        if isinstance(initial, list):
            writes = [f'_ <- rpush Reply {TAG} (jobs b"mail") {tet(value)};' for value in initial]
            declarations += [f'def seedScript : Script Reply {TAG} := do {{ ' + ' '.join(writes)
                + f' pure Reply {TAG} (status b"OK") }}',
                f'def seeded : Client Reply := do {{ _ <- inv Reply {TAG} seedScript; {entry} }}']
    return '\n'.join(declarations) + '\n'


def wire(expected, kind):
    if kind == 'array':
        return ('array:[' + ','.join('bulk:' + value.hex() for value in expected) + ']').encode()
    return kind.encode() + b':' + expected.hex().encode()


def stdout(expected, kind):
    if kind == 'array':
        return json.dumps([v.decode('utf-8') for v in expected], ensure_ascii=False,
                          separators=(',', ':')).replace('\x7f', '\\u007f').encode() + b'\n'
    return expected + b'\n'


def emit(work, path, entry):
    output = work / ('out-' + entry)
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(not body.startswith(b'#!lua flags=no-writes\n'), 'LIST-BULK write classification')
    return output


def twin(work, output, initial, expected, after, kind):
    support.lua(work, output, initial, wire(expected, kind) if kind == 'array' else expected, after, kind)


def offline(work, outputs):
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        twin(work, outputs[entry], initial, expected, after, kind)
        seed = initial.decode() if isinstance(initial, bytes) else '@hash' if isinstance(initial, dict) else '@set' if isinstance(initial, set) else '@missing'
        (work / 'ListBulkCases.tet').write_text(source(i))
        rows = []
        code = support.checker.check(work, 'ListBulkCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
            'ListBulkCases.tet', 'seeded' if isinstance(initial, list) else entry, KEY, seed, '1000000'], receive=rows.append)
        require(code == 0 and rows == [b'REPLY ' + wire(expected, kind) + b'\n'], f'LIST-BULK store reply {i}: {rows!r}')
    print('PASS LIST-BULK-ORACLES store=23 luajit=23', flush=True)


def refusals(work):
    invalid = []
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    for name in ('lpushMany', 'rpushMany'):
        cmd = command(name, [b'a'])
        invalid.append((cmd.replace(TAG, '(tag b"elsewhere")'), 'List', mismatch + b'(In SMu Tag [] (ACtor tag)'))
        invalid += [(cmd, schema, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode())
                    for schema, ctor in [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('Set', 'Set'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]]
        invalid += [(cmd.replace(arguments([b'a']), bad), 'List', b'CHECK unbound: ' + reason) for bad, reason in
                    [('b"a"', b'bytesCons is not a constructor of BulkArgs'),
                     ('repliesNil', b'repliesNil is not a constructor of BulkArgs'),
                     ('(bulkOne nil)', b'nil is not a constructor of Bytes'),
                     ('(bulkMore b"a" repliesNil)', b'repliesNil is not a constructor of BulkArgs')]]
    for i, (body, schema, diagnostic) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{i}'
        path.write_text(f'module Refused\nschema jobs : String -> Key {schema} tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ r <- {body}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'LIST-BULK refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'LIST-BULK refusal published output {i}')
    require(len(invalid) == 20, 'LIST-BULK refusal inventory')
    print('PASS LIST-BULK-REFUSALS cases=20 atomic_output=20', flush=True)


def live(work, outputs):
    hosts = rejected = errors = 0
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        live_cases = cases() + [(entry, kind, WRONG, kind, 'status')
                                for entry in ('left', 'right') for kind in ('zset', 'stream')]
        for entry, initial, expected, after, kind in live_cases:
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                if isinstance(initial, (set, list)):
                    operation = 'SADD' if isinstance(initial, set) else 'RPUSH'
                    for value in initial:
                        run(redis + ['EVAL', f"return redis.call('{operation}',KEYS[1]," + support.literal(value) + ')', '1', KEY])
                elif isinstance(initial, dict):
                    for field, value in initial.items():
                        run(redis + ['EVAL', "return redis.call('HSET',KEYS[1]," + support.literal(field) + ',' + support.literal(value) + ')', '1', KEY])
                elif initial == 'zset':
                    run(redis + ['ZADD', KEY, '1', 'm'])
                elif initial == 'stream':
                    run(redis + ['XADD', KEY, '*', 'f', 'v'])
                elif initial is not None:
                    run(redis + ['-x', 'SET', KEY], data=initial)
                run(redis + ['PEXPIREAT', KEY, '4102444800000'])
                before, deadline = run(redis + ['DUMP', KEY]), run(redis + ['PEXPIRETIME', KEY])
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                try:
                    wanted, code = stdout(expected, kind), 0
                except UnicodeDecodeError:
                    wanted, code = b'', 4
                require(run(args, env=env, code=code) == wanted, f'LIST-BULK {host} {entry} reply')
                if isinstance(after, list):
                    check = ('local got=redis.call("LRANGE",KEYS[1],0,-1); local want=' + support.lua_items(after)
                             + '; if #got ~= #want then return 0 end; for i=1,#want do if got[i] ~= want[i] then return 0 end end; return 1')
                    require(run(redis + ['EVAL', check, '1', KEY]) == b'1\n', 'LIST-BULK live complete list order')
                    expected_deadline = b'-1\n' if initial is None else deadline
                    require(run(redis + ['PEXPIRETIME', KEY]) == expected_deadline, 'LIST-BULK preserves expiry')
                elif after is None:
                    require(run(redis + ['EXISTS', KEY]) == b'0\n', 'LIST-BULK retained reply survives deletion')
                else:
                    require(run(redis + ['DUMP', KEY]) == before and run(redis + ['PEXPIRETIME', KEY]) == deadline,
                            'LIST-BULK wrong type preserves complete state')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'LIST-BULK unrelated key')
                hosts, rejected = hosts + 1, rejected + int(code != 0)
        for host in ('node', 'bash'):
            run(redis + ['FLUSHDB'])
            run(redis + ['SET', KEY, 'wrong'])
            output = outputs['raw']
            args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                    if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
            require(run(args, env=env, code=4) == b'', 'LIST-BULK error stops host')
            require(run(redis + ['GET', KEY]) == b'wrong\n', 'LIST-BULK error preserves value')
            hosts, errors = hosts + 1, errors + 1
    require((hosts, rejected, errors) == (56, 2, 2), 'LIST-BULK host inventory')
    print(f'PASS LIST-BULK-E2E cases={len(live_cases)} hosts={hosts} utf8_refusals={rejected} errors={errors}', flush=True)
    count = 0
    for entry, expected in EXAMPLES.items():
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/QueueBatch.tet', '--entry', entry, '--host', host]) == expected,
                    f'LIST-BULK example {entry} {host}')
            count += 1
    print(f'PASS LIST-BULK-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline']), 'Usage: list-bulk-tests.py [--static|--offline|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-list-bulk-') as temporary:
        work = Path(temporary)
        path = work / 'ListBulkCases.tet'
        path.write_text(source())
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(entry in ENTRIES and bool(rows), 'LIST-BULK probe must have cases')
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                twin(work, output, initial, expected, after, kind)
            print(f'PASS LIST-BULK-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, path, entry) for entry in ENTRIES}
        print(f'PASS LIST-BULK-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES.items():
            require(run(['./tether', 'run', 'examples/QueueBatch.tet', '--entry', entry]) == expected, 'LIST-BULK interpreter example')
        if '--static' not in sys.argv:
            offline(work, outputs)
        if not sys.argv[1:]:
            live(work, outputs)
    print('PASS LIST-BULK-TESTS' + (f' mode={sys.argv[1][2:]}' if sys.argv[1:] else ''), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-BULK-TESTS {error}', file=sys.stderr)
        sys.exit(1)
