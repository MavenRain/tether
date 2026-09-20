#!/usr/bin/env python3
"""LINSERT checks replies, complete ordered state, expiry and host transports."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('list_insert_support', ROOT / 'dev/lists-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, tet = support.run, support.require, support.tet
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
VALUES = [b'a', b'b', b'a', b'c', b'a']
BINARY, REVERSED = bytes(range(256)), bytes(reversed(range(256)))
QUERY = {
    'before': ('Before', b'a', b'x'), 'after': ('After', b'a', b'x'),
    'tailBefore': ('Before', b'c', b'x'), 'tailAfter': ('After', b'c', b'x'),
    'emptyPivot': ('Before', b'', b'x'), 'emptyValue': ('After', b'a', b''),
    'binaryBefore': ('Before', BINARY, REVERSED), 'binaryAfter': ('After', BINARY, REVERSED),
    'same': ('After', b'a', b'a'), 'numeric': ('Before', b'01', b'x'),
    'computedBefore': ('Before', b'a', b'x'), 'computedAfter': ('After', b'a', b'x'),
    'within': ('Before', b'a', b'x'), 'snapshot': ('After', b'a', b'x'),
    'rawBefore': ('Before', b'a', b'x'), 'rawAfter': ('After', b'a', b'x'),
}
ENTRIES = tuple(QUERY) + ('earlier',)
WRITES = ('before', 'after')
EXAMPLES = {'main': b'["welcome:alice","priority:carol","welcome:bob","audit:bob"]\n',
            'length': b'4\n', 'missingPivot': b'-1\n'}


def command(side, pivot, value):
    return f'linsert{side} Reply {TAG} (jobs b"mail") {tet(pivot)} {tet(value)}'


def cases():
    before = [b'x', b'a', b'b', b'a', b'c', b'a']
    after = [b'a', b'x', b'b', b'a', b'c', b'a']
    rows = []
    for entry, full, single in [('before', before, [b'x', b'a']), ('after', after, [b'a', b'x'])]:
        rows += [(entry, None, b'0', None, 'int'), (entry, [b'z'], b'-1', [b'z'], 'int'),
                 (entry, VALUES, b'6', full, 'int'), (entry, [b'a'], b'2', single, 'int')]
    rows += [
        ('tailBefore', [b'p', b'q', b'c', b'r'], b'5', [b'p', b'q', b'x', b'c', b'r'], 'int'),
        ('tailAfter', [b'p', b'q', b'c', b'r'], b'5', [b'p', b'q', b'c', b'x', b'r'], 'int'),
        ('emptyPivot', [b'', b'a', b''], b'4', [b'x', b'', b'a', b''], 'int'),
        ('emptyValue', [b'a', b'b'], b'3', [b'a', b'', b'b'], 'int'),
        ('binaryBefore', [BINARY, b'a', BINARY], b'4', [REVERSED, BINARY, b'a', BINARY], 'int'),
        ('binaryAfter', [BINARY, b'a', BINARY], b'4', [BINARY, REVERSED, b'a', BINARY], 'int'),
        ('same', [b'a', b'a'], b'3', [b'a', b'a', b'a'], 'int'),
        ('numeric', [b'1', b'01', b'01'], b'4', [b'1', b'x', b'01', b'01'], 'int'),
        ('computedBefore', VALUES, b'6', before, 'int'), ('computedAfter', VALUES, b'6', after, 'int'),
        ('within', VALUES, b'6', None, 'int'), ('earlier', VALUES, b'6', None, 'int'),
        ('snapshot', VALUES, after, after, 'array'),
        ('rawBefore', None, b'0', None, 'int'), ('rawAfter', None, b'0', None, 'int'),
    ]
    for initial in ([support.TEXT, b'a', b'"\n$(touch forbidden)\\'], [bytes([255]), b'a']):
        result = initial[:2] + [b'x'] + initial[2:]
        rows.append(('snapshot', initial, result, result, 'array'))
    rows += [(entry, initial, WRONG, initial, 'status') for entry in WRITES
             for initial in (b'wrong', {b'f': b'v'}, {b'm'})]
    require(len(rows) == 31, 'LIST-INSERT case inventory')
    return rows


def source(seed=None):
    declarations = ['module ListInsertCases', 'schema jobs : String -> Key List tag b"queue"',
        'def identity : Bytes -> Bytes := fun (value : Bytes) => value',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        f'def removeScript : Script Reply {TAG} := do {{ r <- del Reply List {TAG} (jobs b"mail"); pure Reply {TAG} r }}']
    for entry, (side, pivot, value) in QUERY.items():
        cmd = command(side, pivot, value)
        if entry.startswith('computed'):
            cmd = cmd.replace(tet(pivot), f'(identity {tet(pivot)})').replace(tet(value), f'(identity {tet(value)})')
        next_step = (f'_ <- del Reply List {TAG} (jobs b"mail"); ' if entry == 'within' else
            f'view <- lrange Reply {TAG} (jobs b"mail") (int64 b"0") (int64 b"-1"); ' if entry == 'snapshot' else '')
        result = 'view' if entry == 'snapshot' else 'expose r'
        body = (f'{cmd} (fun (r : Reply) => pure Reply {TAG} r)' if entry.startswith('raw') else
                f'do {{ r <- {cmd}; {next_step}pure Reply {TAG} ({result}) }}')
        declarations += [f'def {entry}Script : Script Reply {TAG} := {body}',
            f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; done Reply r }}']
    declarations += [f'def earlier : Client Reply := do {{ r <- inv Reply {TAG} afterScript; '
        f'_ <- inv Reply {TAG} removeScript; done Reply r }}']
    if seed is not None:
        entry, initial, *_ = cases()[seed]
        if isinstance(initial, list):
            writes = ' '.join(f'_ <- rpush Reply {TAG} (jobs b"mail") {tet(value)};' for value in initial)
            declarations += [f'def seedScript : Script Reply {TAG} := do {{ {writes} pure Reply {TAG} nil }}',
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
        require(not body.startswith(b'#!lua flags=no-writes\n'), 'LIST-INSERT write classification')
    return output


def twin(work, output, initial, expected, after, kind):
    support.lua(work, output, initial, wire(expected, kind) if kind == 'array' else expected, after, kind)


def offline(work, outputs):
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        twin(work, outputs[entry], initial, expected, after, kind)
        seed = initial.decode() if isinstance(initial, bytes) else '@hash' if isinstance(initial, dict) else '@set' if isinstance(initial, set) else '@missing'
        (work / 'ListInsertCases.tet').write_text(source(i))
        rows = []
        code = support.checker.check(work, 'ListInsertCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
            'ListInsertCases.tet', 'seeded' if isinstance(initial, list) else entry, KEY, seed, '1000000'], receive=rows.append)
        require(code == 0 and rows == [b'REPLY ' + wire(expected, kind) + b'\n'], f'LIST-INSERT store reply {i}: {rows!r}')
    print('PASS LIST-INSERT-ORACLES store=31 luajit=31', flush=True)


def refusals(work):
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = []
    for side in ('Before', 'After'):
        cmd = command(side, b'a', b'x')
        invalid += [(cmd.replace(TAG, '(tag b"elsewhere")'), 'List', mismatch + b'(In SMu Tag [] (ACtor tag)')]
        invalid += [(cmd, schema, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode()) for schema, ctor in
                    [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('Set', 'Set'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]]
        invalid += [(cmd.replace(tet(value), '(int64 b"1")'), 'List',
                     b'CHECK unbound: signed64Bytes is not a constructor of Bytes') for value in (b'a', b'x')]
    for i, (body, schema, diagnostic) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{i}'
        path.write_text(f'module Refused\nschema jobs : String -> Key {schema} tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ r <- {body}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'LIST-INSERT refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'LIST-INSERT refusal published output {i}')
    require(len(invalid) == 16, 'LIST-INSERT refusal inventory')
    print('PASS LIST-INSERT-REFUSALS cases=16 atomic_output=16', flush=True)


def live(work, outputs):
    hosts = rejected = errors = expired = 0
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        live_cases = cases() + [(entry, kind, WRONG, kind, 'status') for entry in WRITES for kind in ('zset', 'stream')]
        def args(output, host):
            return (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                    if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
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
                try:
                    wanted, code = stdout(expected, kind), 0
                except UnicodeDecodeError:
                    wanted, code = b'', 4
                actual = run(args(outputs[entry], host), env=env, code=code)
                require(actual == wanted, f'LIST-INSERT {host} {entry} reply: {actual!r} != {wanted!r}')
                if isinstance(after, list):
                    check = ('local got=redis.call("LRANGE",KEYS[1],0,-1); local want=' + support.lua_items(after)
                             + '; if #got ~= #want then return 0 end; for i=1,#want do if got[i] ~= want[i] then return 0 end end; return 1')
                    require(run(redis + ['EVAL', check, '1', KEY]) == b'1\n', 'LIST-INSERT live complete list order')
                    require(run(redis + ['PEXPIRETIME', KEY]) == deadline, 'LIST-INSERT preserves expiry')
                elif after is None:
                    require(run(redis + ['EXISTS', KEY]) == b'0\n' and run(redis + ['PEXPIRETIME', KEY]) == b'-2\n',
                            'LIST-INSERT deletes empty key and expiry')
                else:
                    require(run(redis + ['DUMP', KEY]) == before and run(redis + ['PEXPIRETIME', KEY]) == deadline,
                            'LIST-INSERT wrong type preserves complete state')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'LIST-INSERT unrelated key')
                hosts, rejected = hosts + 1, rejected + int(code != 0)
        for entry in ('rawBefore', 'rawAfter'):
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', KEY, 'wrong'])
                require(run(args(outputs[entry], host), env=env, code=4) == b'', 'LIST-INSERT error stops host')
                require(run(redis + ['GET', KEY]) == b'wrong\n', 'LIST-INSERT error preserves value')
                hosts, errors = hosts + 1, errors + 1
        for entry in WRITES:
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', KEY, 'expired wrong type'])
                run(redis + ['PEXPIREAT', KEY, '1'])
                require(run(args(outputs[entry], host), env=env) == b'0\n', 'LIST-INSERT expired reply')
                require(run(redis + ['EXISTS', KEY]) == b'0\n' and run(redis + ['PEXPIRETIME', KEY]) == b'-2\n',
                        'LIST-INSERT expired key stays absent')
                hosts, expired = hosts + 1, expired + 1
    require((hosts, rejected, errors, expired) == (78, 2, 4, 4), f'LIST-INSERT host inventory: {(hosts, rejected, errors, expired)}')
    print(f'PASS LIST-INSERT-E2E cases={len(live_cases)} hosts={hosts} utf8_refusals={rejected} errors={errors} expired={expired}', flush=True)
    count = 0
    for entry, expected in EXAMPLES.items():
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/QueueInsert.tet', '--entry', entry, '--host', host]) == expected,
                    f'LIST-INSERT example {entry} {host}')
            count += 1
    print(f'PASS LIST-INSERT-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline']), 'Usage: list-insert-tests.py [--static|--offline|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-list-insert-') as temporary:
        work = Path(temporary)
        path = work / 'ListInsertCases.tet'
        path.write_text(source())
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(entry in ENTRIES and bool(rows), 'LIST-INSERT probe must have cases')
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                twin(work, output, initial, expected, after, kind)
            print(f'PASS LIST-INSERT-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, path, entry) for entry in ENTRIES}
        print(f'PASS LIST-INSERT-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES.items():
            require(run(['./tether', 'run', 'examples/QueueInsert.tet', '--entry', entry]) == expected, 'LIST-INSERT interpreter example')
        if '--static' not in sys.argv:
            offline(work, outputs)
        if not sys.argv[1:]:
            live(work, outputs)
    print('PASS LIST-INSERT-TESTS' + (f' mode={sys.argv[1][2:]}' if sys.argv[1:] else ''), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-INSERT-TESTS {error}', file=sys.stderr)
        sys.exit(1)
