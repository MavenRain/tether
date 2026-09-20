#!/usr/bin/env python3
"""LREM replies, complete state and transport behavior against independent oracles."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('list_remove_support', ROOT / 'dev/lists-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, tet = support.run, support.require, support.tet
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
RANGE = b'ERR value is out of range, value must between -9223372036854775807 and 9223372036854775807'
VALUES = [b'a', b'b', b'a', b'c', b'a']
QUERY = {
    'head': ('1', b'a'), 'two': ('2', b'a'), 'tail': ('-1', b'a'), 'tailTwo': ('-2', b'a'),
    'all': ('0', b'a'), 'max': ('9223372036854775807', b'a'), 'min': ('-9223372036854775807', b'a'),
    'minimum': ('-9223372036854775808', b'a'), 'rawMin': ('-9223372036854775808', b'a'),
    'large': ('9007199254740993', b'a'), 'negativeLarge': ('-9007199254740993', b'a'),
    'empty': ('0', b''), 'binary': ('-1', bytes(range(256))), 'computed': ('0', b'a'),
    'within': ('0', b'a'), 'snapshot': ('0', b'a'), 'raw': ('1', b'a'),
}
ENTRIES = tuple(QUERY) + ('earlier',)
WRITES = ('head', 'tail', 'all')
EXAMPLES = {'main': b'["welcome:alice","welcome:bob"]\n', 'removed': b'2\n', 'retained': b'2\n'}


def command(count, value):
    return f'lrem Reply {TAG} (jobs b"mail") (int64 b"{count}") {tet(value)}'


def cases():
    inputs = [(entry, initial) for entry in WRITES for initial in (None, VALUES, [b'a'], [b'z'])]
    inputs += [(entry, VALUES) for entry in ('two', 'tailTwo', 'max', 'min', 'large', 'negativeLarge')]
    inputs += [('empty', [b'', b'a', b'']), ('binary', [bytes(range(256)), b'a', bytes(range(256))])]
    inputs += [(entry, VALUES) for entry in ('computed', 'within', 'earlier', 'snapshot')]
    inputs += [('snapshot', [support.TEXT, b'a', b'"\n$(touch forbidden)\\']),
               ('snapshot', [bytes([255]), b'a']), ('raw', None)]
    inputs += [(entry, initial) for entry in WRITES for initial in (b'wrong', {b'f': b'v'}, {b'm'})]
    inputs += [('minimum', initial) for initial in (None, VALUES, b'wrong', {b'f': b'v'}, {b'm'})]
    rows = []
    for entry, initial in inputs:
        if entry == 'minimum':
            rows.append((entry, initial, RANGE, initial, 'status'))
            continue
        if initial is not None and not isinstance(initial, list):
            rows.append((entry, initial, WRONG, initial, 'status'))
            continue
        count, value = QUERY['all' if entry == 'earlier' else entry]
        count = int(count)
        indices = [i for i, item in enumerate(initial or []) if item == value]
        selected = indices if count == 0 else indices[:count] if count > 0 else indices[count:]
        after = [item for i, item in enumerate(initial or []) if i not in selected] or None
        expected, kind = (after or [], 'array') if entry == 'snapshot' else (str(len(selected)).encode(), 'int')
        rows.append((entry, initial, expected, None if entry in ('within', 'earlier') else after, kind))
    require(len(rows) == 41, 'LIST-REMOVE case inventory')
    return rows


def source(seed=None):
    declarations = ['module ListRemoveCases', 'schema jobs : String -> Key List tag b"queue"',
        'def identity : Bytes -> Bytes := fun (b : Bytes) => b',
        'def keepCount : Signed64 -> Signed64 := fun (n : Signed64) => n',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        f'def removeScript : Script Reply {TAG} := do {{ r <- del Reply List {TAG} (jobs b"mail"); pure Reply {TAG} r }}']
    for entry, (count, value) in QUERY.items():
        cmd = command(count, value)
        if entry == 'computed':
            cmd = cmd.replace(f'(int64 b"{count}")', f'(keepCount (int64 b"{count}"))').replace(tet(value), f'(identity {tet(value)})')
        next_step = (f'_ <- del Reply List {TAG} (jobs b"mail"); ' if entry == 'within' else
            f'view <- lrange Reply {TAG} (jobs b"mail") (int64 b"0") (int64 b"-1"); ' if entry == 'snapshot' else '')
        result = 'view' if entry == 'snapshot' else 'expose r'
        body = (f'{cmd} (fun (r : Reply) => pure Reply {TAG} r)' if entry in ('raw', 'rawMin') else
                f'do {{ r <- {cmd}; {next_step}pure Reply {TAG} ({result}) }}')
        declarations += [f'def {entry}Script : Script Reply {TAG} := {body}',
            f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; done Reply r }}']
    declarations += [f'def earlier : Client Reply := do {{ r <- inv Reply {TAG} allScript; '
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
        require(not body.startswith(b'#!lua flags=no-writes\n'), 'LIST-REMOVE write classification')
    return output


def twin(work, output, initial, expected, after, kind):
    support.lua(work, output, initial, wire(expected, kind) if kind == 'array' else expected, after, kind)


def offline(work, outputs):
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        twin(work, outputs[entry], initial, expected, after, kind)
        seed = initial.decode() if isinstance(initial, bytes) else '@hash' if isinstance(initial, dict) else '@set' if isinstance(initial, set) else '@missing'
        (work / 'ListRemoveCases.tet').write_text(source(i))
        rows = []
        code = support.checker.check(work, 'ListRemoveCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
            'ListRemoveCases.tet', 'seeded' if isinstance(initial, list) else entry, KEY, seed, '1000000'], receive=rows.append)
        require(code == 0 and rows == [b'REPLY ' + wire(expected, kind) + b'\n'], f'LIST-REMOVE store reply {i}: {rows!r}')
    print('PASS LIST-REMOVE-ORACLES store=41 luajit=41', flush=True)


def refusals(work):
    cmd = command('1', b'a')
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = [(cmd.replace(TAG, '(tag b"elsewhere")'), 'List', mismatch + b'(In SMu Tag [] (ACtor tag)')]
    invalid += [(cmd, schema, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode()) for schema, ctor in
                [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('Set', 'Set'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]]
    invalid += [(cmd.replace('(int64 b"1")', 'b"1"'), 'List', b'CHECK unbound: bytesCons is not a constructor of Signed64'),
                (cmd.replace(tet(b'a'), '(int64 b"1")'), 'List', b'CHECK unbound: signed64Bytes is not a constructor of Bytes')]
    invalid += [(cmd.replace('int64 b"1"', f'int64 {tet(value)}'), 'List', b'INT64') for value in
                [b'', b'01', b'-0', b'+1', b'1.0', b' 1', b'1\x00', b'9223372036854775808', b'-9223372036854775809']]
    for i, (body, schema, diagnostic) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{i}'
        path.write_text(f'module Refused\nschema jobs : String -> Key {schema} tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ r <- {body}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'LIST-REMOVE refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'LIST-REMOVE refusal published output {i}')
    require(len(invalid) == 17, 'LIST-REMOVE refusal inventory')
    print('PASS LIST-REMOVE-REFUSALS cases=17 atomic_output=17', flush=True)


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
                require(actual == wanted, f'LIST-REMOVE {host} {entry} reply: {actual!r} != {wanted!r}')
                if isinstance(after, list):
                    check = ('local got=redis.call("LRANGE",KEYS[1],0,-1); local want=' + support.lua_items(after)
                             + '; if #got ~= #want then return 0 end; for i=1,#want do if got[i] ~= want[i] then return 0 end end; return 1')
                    require(run(redis + ['EVAL', check, '1', KEY]) == b'1\n', 'LIST-REMOVE live complete list order')
                    require(run(redis + ['PEXPIRETIME', KEY]) == deadline, 'LIST-REMOVE preserves expiry')
                elif after is None:
                    require(run(redis + ['EXISTS', KEY]) == b'0\n' and run(redis + ['PEXPIRETIME', KEY]) == b'-2\n',
                            'LIST-REMOVE deletes empty key and expiry')
                else:
                    require(run(redis + ['DUMP', KEY]) == before and run(redis + ['PEXPIRETIME', KEY]) == deadline,
                            'LIST-REMOVE wrong type preserves complete state')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'LIST-REMOVE unrelated key')
                hosts, rejected = hosts + 1, rejected + int(code != 0)
        for entry in ('raw', 'rawMin'):
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', KEY, 'wrong'])
                require(run(args(outputs[entry], host), env=env, code=4) == b'', 'LIST-REMOVE error stops host')
                require(run(redis + ['GET', KEY]) == b'wrong\n', 'LIST-REMOVE error preserves value')
                hosts, errors = hosts + 1, errors + 1
        for entry in WRITES:
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', KEY, 'expired wrong type'])
                run(redis + ['PEXPIREAT', KEY, '1'])
                require(run(args(outputs[entry], host), env=env) == b'0\n', 'LIST-REMOVE expired reply')
                require(run(redis + ['EXISTS', KEY]) == b'0\n' and run(redis + ['PEXPIRETIME', KEY]) == b'-2\n',
                        'LIST-REMOVE expired key stays absent')
                hosts, expired = hosts + 1, expired + 1
    require((hosts, rejected, errors, expired) == (104, 2, 4, 6), f'LIST-REMOVE host inventory: {(hosts, rejected, errors, expired)}')
    print(f'PASS LIST-REMOVE-E2E cases={len(live_cases)} hosts={hosts} utf8_refusals={rejected} errors={errors} expired={expired}', flush=True)
    count = 0
    for entry, expected in EXAMPLES.items():
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/QueueCleanup.tet', '--entry', entry, '--host', host]) == expected,
                    f'LIST-REMOVE example {entry} {host}')
            count += 1
    print(f'PASS LIST-REMOVE-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline']), 'Usage: list-remove-tests.py [--static|--offline|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-list-remove-') as temporary:
        work = Path(temporary)
        path = work / 'ListRemoveCases.tet'
        path.write_text(source())
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(entry in ENTRIES and bool(rows), 'LIST-REMOVE probe must have cases')
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                twin(work, output, initial, expected, after, kind)
            print(f'PASS LIST-REMOVE-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, path, entry) for entry in ENTRIES}
        print(f'PASS LIST-REMOVE-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES.items():
            require(run(['./tether', 'run', 'examples/QueueCleanup.tet', '--entry', entry]) == expected, 'LIST-REMOVE interpreter example')
        if '--static' not in sys.argv:
            offline(work, outputs)
        if not sys.argv[1:]:
            live(work, outputs)
    print('PASS LIST-REMOVE-TESTS' + (f' mode={sys.argv[1][2:]}' if sys.argv[1:] else ''), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        print(f'FAIL LIST-REMOVE-TESTS {error}', file=sys.stderr)
        sys.exit(1)
