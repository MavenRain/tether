#!/usr/bin/env python3
"""Ordered nullable Hash projections across the store, twin and live hosts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hmget_support', ROOT / 'dev/lists-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, tet = support.run, support.require, support.tet
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
QUERY = {
    'lookup': [b'missing', b'z', b'a', b'absent', b'z', b''],
    'one': [b'z'],
    'repeat': [b'z', b'z', b'z'],
    'many': [f'f{i:03}'.encode() for i in range(129)],
    'binary': [support.BINARY, b'', support.BINARY, b'none'],
    'head': [b'missing', b'z'],
}
QUERY['raw'] = QUERY['within'] = QUERY['computed'] = QUERY['lookup']
ENTRIES = tuple(QUERY) + ('earlier',)
READONLY = {name + 'Script' for name in QUERY if name != 'within'}
EXAMPLE = b'["member",null,"Alice","member"]\n'


def arguments(fields):
    require(bool(fields), 'HMGET nonempty test field list')
    result = f'(bulkOne {tet(fields[-1])})'
    for field in reversed(fields[:-1]):
        result = f'(bulkMore {tet(field)} {result})'
    return result


def command(fields):
    return f'hmget Reply {TAG} (jobs b"mail") {arguments(fields)}'


def cases():
    inputs = [
        ('lookup', None), ('lookup', {b'z': b'Z', b'a': b'A', b'': b''}),
        ('lookup', {b'z': b'"\n$(touch forbidden)\\', b'a': support.TEXT}),
        ('one', None), ('one', {b'z': b'9007199254740993'}), ('one', {b'z': b''}),
        ('repeat', None), ('repeat', {b'z': b'copy'}),
        ('binary', {support.BINARY: b'valid', b'': b''}),
        ('binary', {support.BINARY: bytes(range(256)), b'': b''}),
        ('many', {f'f{i:03}'.encode(): f'v{128-i:03}'.encode() for i in range(0, 129, 2)}),
        ('within', {b'z': b'old', b'a': b'before'}),
        ('earlier', {b'z': b'old', b'a': b'before'}),
        ('head', {b'z': b'present'}),
        ('computed', {b'z': b'Z', b'a': b'A'}),
        ('lookup', b'wrong'), ('lookup', [b'm']), ('lookup', {b'm'}),
    ]
    rows = []
    for entry, initial in inputs:
        if initial is not None and not isinstance(initial, dict):
            rows.append((entry, initial, WRONG, initial, 'status'))
            continue
        expected = [(initial or {}).get(field) for field in QUERY['lookup' if entry == 'earlier' else entry]]
        if entry == 'head':
            rows.append((entry, initial, None, initial, 'null'))
        else:
            rows.append((entry, initial, expected, None if entry in ('within', 'earlier') else initial, 'array'))
    require(len(rows) == 18, 'HMGET case inventory')
    return rows


def source(seed=None):
    declarations = ['module HmgetCases', 'schema jobs : String -> Key Hash tag b"queue"',
        'def prepend : Bytes -> BulkArgs -> BulkArgs := fun (b : Bytes) (rest : BulkArgs) => bulkMore b rest',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        'def first : Replies -> Reply := fun (rs : Replies) => case rs as x in Replies return Reply with',
        '| repliesNil => nil | repliesCons r rest => r',
        'def headReply : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => first rs',
        f'def removeScript : Script Reply {TAG} := do {{ r <- del Reply Hash {TAG} (jobs b"mail"); pure Reply {TAG} r }}']
    for entry, fields in QUERY.items():
        result = 'r' if entry == 'raw' else 'headReply r' if entry == 'head' else 'expose r'
        mutation = f'_ <- del Reply Hash {TAG} (jobs b"mail"); ' if entry == 'within' else ''
        cmd = command(fields)
        if entry == 'computed':
            cmd = cmd.replace(arguments(fields), f'(prepend {tet(fields[0])} {arguments(fields[1:])})')
        declarations += [f'def {entry}Script : Script Reply {TAG} := do {{ r <- {cmd}; '
            f'{mutation}pure Reply {TAG} ({result}) }}',
            f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; done Reply r }}']
    declarations += [f'def earlier : Client Reply := do {{ r <- inv Reply {TAG} lookupScript; '
        f'_ <- inv Reply {TAG} removeScript; done Reply r }}']
    if seed is not None:
        entry, initial, *_ = cases()[seed]
        if isinstance(initial, dict):
            writes = [f'_ <- hset Reply {TAG} (jobs b"mail") {tet(f)} {tet(v)};' for f, v in initial.items()]
            declarations += [f'def seedScript : Script Reply {TAG} := do {{ ' + ' '.join(writes)
                + f' pure Reply {TAG} (status b"OK") }}',
                f'def seeded : Client Reply := do {{ _ <- inv Reply {TAG} seedScript; {entry} }}']
    return '\n'.join(declarations) + '\n'


def wire(expected, kind):
    if kind == 'array':
        return ('array:[' + ','.join('null' if v is None else 'bulk:' + v.hex() for v in expected) + ']').encode()
    return b'null' if kind == 'null' else kind.encode() + b':' + expected.hex().encode()


def stdout(expected, kind):
    if kind == 'array':
        values = [None if v is None else v.decode('utf-8') for v in expected]
        return json.dumps(values, ensure_ascii=False, separators=(',', ':')).replace('\x7f', '\\u007f').encode() + b'\n'
    return (expected or b'') + b'\n'


def emit(work, path, entry):
    output = work / ('out-' + entry)
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(body.startswith(b'#!lua flags=no-writes\n') == (script['entry'] in READONLY), 'HMGET write classification')
    return output


def twin(work, output, initial, expected, after, kind):
    value = wire(expected, kind) if kind == 'array' else (expected or b'')
    support.lua(work, output, initial, value, after, kind)


def offline(work, outputs):
    stores = twins = 0
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        twin(work, outputs[entry], initial, expected, after, kind)
        twins += 1
        seed = (initial.decode() if isinstance(initial, bytes) else '@set' if isinstance(initial, set)
                else '@list' if isinstance(initial, list) else '@missing')
        (work / 'HmgetCases.tet').write_text(source(i))
        rows = []
        code = support.checker.check(work, 'HmgetCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
            'HmgetCases.tet', 'seeded' if isinstance(initial, dict) else entry, KEY, seed, '1000000'], receive=rows.append)
        require(code == 0 and rows == [b'REPLY ' + wire(expected, kind) + b'\n'], f'HMGET store reply {i}: {rows!r}')
        stores += 1
    print(f'PASS HMGET-ORACLES store={stores} luajit={twins}', flush=True)


def refusals(work):
    cmd = command([b'a'])
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = [(cmd.replace(TAG, '(tag b"elsewhere")'), 'Hash', mismatch + b'(In SMu Tag [] (ACtor tag)')]
    invalid += [(cmd, schema, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode())
                for schema, ctor in [('(Str Binary)', 'Str'), ('Set', 'Set'), ('List', 'List'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]]
    unbound = b'CHECK unbound: '
    invalid += [(cmd.replace(arguments([b'a']), bad), 'Hash', unbound + reason) for bad, reason in
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
        require(result.returncode == 2 and diagnostic in result.stderr, f'HMGET refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'HMGET refusal published output {i}')
    print(f'PASS HMGET-REFUSALS cases={len(invalid)} atomic_output={len(invalid)}', flush=True)


def live(work, outputs):
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        hosts = readonly = rejected = errors = 0
        live_cases = cases() + [('lookup', kind, WRONG, kind, 'status') for kind in ('zset', 'stream')]
        for entry, initial, expected, after, kind in live_cases:
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                if isinstance(initial, (set, list)):
                    operation = 'SADD' if isinstance(initial, set) else 'RPUSH'
                    for value in sorted(initial):
                        run(redis + ['EVAL', f"return redis.call('{operation}',KEYS[1]," + support.literal(value) + ')', '1', KEY])
                elif isinstance(initial, dict):
                    for field, value in reversed(sorted(initial.items())):
                        run(redis + ['EVAL', "return redis.call('HSET',KEYS[1]," + support.literal(field) + ',' + support.literal(value) + ')', '1', KEY])
                elif initial == 'zset':
                    run(redis + ['ZADD', KEY, '1', 'm'])
                elif initial == 'stream':
                    run(redis + ['XADD', KEY, '*', 'f', 'v'])
                elif initial is not None:
                    run(redis + ['-x', 'SET', KEY], data=initial)
                run(redis + ['PEXPIREAT', KEY, '4102444800000'])
                before, deadline = run(redis + ['DUMP', KEY]), run(redis + ['PEXPIRETIME', KEY])
                ro = entry not in ('within', 'earlier')
                run(redis + ['ACL', 'SETUSER', 'default', '-eval' if ro else '+eval', '-evalsha' if ro else '+evalsha'])
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                try:
                    wanted, code = stdout(expected, kind), 0
                except UnicodeDecodeError:
                    wanted, code = b'', 4
                require(run(args, env=env, code=code) == wanted, f'HMGET {host} {entry} reply')
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                if after == initial:
                    require(run(redis + ['DUMP', KEY]) == before and run(redis + ['PEXPIRETIME', KEY]) == deadline,
                            'HMGET preserves value and deadline')
                else:
                    require(run(redis + ['EXISTS', KEY]) == b'0\n', 'HMGET retained reply survives deletion')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'HMGET unrelated key')
                hosts, readonly, rejected = hosts + 1, readonly + int(ro), rejected + int(code != 0)
        for host in ('node', 'bash'):
            run(redis + ['FLUSHDB'])
            run(redis + ['SET', KEY, 'wrong'])
            run(redis + ['ACL', 'SETUSER', 'default', '-eval', '-evalsha'])
            output = outputs['raw']
            args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                    if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
            require(run(args, env=env, code=4) == b'', 'HMGET error stops host')
            require(run(redis + ['GET', KEY]) == b'wrong\n', 'HMGET error preserves value')
            run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
            hosts, readonly, errors = hosts + 1, readonly + 1, errors + 1
        require((hosts, readonly, rejected, errors) == (42, 38, 2, 2), 'HMGET host inventory')
        print(f'PASS HMGET-E2E cases={len(live_cases)} hosts={hosts} readonly={readonly} '
              f'utf8_refusals={rejected} errors={errors}', flush=True)
    count = 0
    for entry in ('main', 'retained'):
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/ProfileFields.tet', '--entry', entry, '--host', host]) == EXAMPLE,
                    f'HMGET example {entry} {host}')
            count += 1
    print(f'PASS HMGET-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline']), 'Usage: hmget-tests.py [--static|--offline|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-hmget-') as temporary:
        work = Path(temporary)
        path = work / 'HmgetCases.tet'
        path.write_text(source())
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(entry in ENTRIES and bool(rows), 'HMGET probe must have cases')
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                twin(work, output, initial, expected, after, kind)
            print(f'PASS HMGET-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, path, entry) for entry in ENTRIES}
        print(f'PASS HMGET-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry in ('main', 'retained'):
            require(run(['./tether', 'run', 'examples/ProfileFields.tet', '--entry', entry]) == EXAMPLE, 'HMGET interpreter example')
        if '--static' not in sys.argv:
            offline(work, outputs)
        if not sys.argv[1:]:
            live(work, outputs)
    print('PASS HMGET-TESTS' + (f' mode={sys.argv[1][2:]}' if sys.argv[1:] else ''), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL HMGET-TESTS {error}', file=sys.stderr)
        sys.exit(1)
