#!/usr/bin/env python3
"""Variadic Hash field deletion across the independent store, twin and live Redis."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hdel_many_support', ROOT / 'dev/lists-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, tet = support.run, support.require, support.tet
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
VALUES = [b'a', b'b', b'a', b'c', b'']
QUERY = {
    'remove': ('hdelMany', VALUES), 'one': ('hdelMany', [b'one']),
    'many': ('hdelMany', [f'v{i:03}'.encode() for i in range(129)]),
    'binary': ('hdelMany', [bytes(range(256)), b'', support.BINARY]),
    'computed': ('hdelMany', VALUES), 'within': ('hdelMany', VALUES),
    'snapshot': ('hdelMany', VALUES), 'raw': ('hdelMany', VALUES),
}
ENTRIES = tuple(QUERY) + ('earlier',)
EXAMPLES = {'main': b'["name","Alice"]\n', 'removed': b'2\n', 'retained': b'2\n'}


def arguments(values):
    require(bool(values), 'HDEL-MANY nonempty test arguments')
    result = f'(bulkOne {tet(values[-1])})'
    for value in reversed(values[:-1]):
        result = f'(bulkMore {tet(value)} {result})'
    return result


def command(name, values):
    return f'{name} Reply {TAG} (jobs b"mail") {arguments(values)}'


def fields(names):
    return {name: b'value:' + name for name in names}


def cases():
    inputs = [
        ('remove', None), ('remove', fields(VALUES)), ('remove', fields([b'a', b'old'])),
        ('remove', fields([b'old'])), ('remove', fields([b'a'])),
        ('one', None), ('one', fields([b'one'])), ('one', fields([b'one', b'old'])),
        ('many', fields([b'v000', b'v128', b'old'])), ('many', fields(QUERY['many'][1])),
        ('binary', fields([bytes(range(256)), support.BINARY, b'', b'old'])), ('binary', None),
        ('computed', fields([b'a', b'b', b'old'])), ('within', fields([b'a', b'b', b'old'])),
        ('earlier', fields([b'a', b'b', b'old'])),
        ('snapshot', {b'a': b'delete', support.TEXT: b'kept', b'quote': support.TEXT}),
        ('snapshot', {b'a': b'delete', b'kept': b'\xff'}), ('raw', fields([b'a'])),
    ]
    inputs += [('remove', value) for value in (b'wrong', {b'm'}, [b'm'])]
    rows = []
    for entry, initial in inputs:
        if initial is not None and not isinstance(initial, dict):
            rows.append((entry, initial, WRONG, initial, 'status'))
            continue
        _, values = QUERY['remove' if entry == 'earlier' else entry]
        old, requested = initial or {}, set(values)
        after = {field: value for field, value in old.items() if field not in requested}
        changed = len(old) - len(after)
        expected, kind = ([item for pair in sorted(after.items()) for item in pair], 'array') if entry == 'snapshot' else (str(changed).encode(), 'int')
        rows.append((entry, initial, expected, None if entry in ('within', 'earlier') else after or None, kind))
    require(len(rows) == 21, 'HDEL-MANY case inventory')
    return rows


def source(seed=None):
    declarations = ['module HdelManyCases', 'schema jobs : String -> Key Hash tag b"queue"',
        'def identity : Bytes -> Bytes := fun (b : Bytes) => b',
        'def keepArgs : BulkArgs -> BulkArgs := fun (args : BulkArgs) => args',
        'def prepend : Bytes -> BulkArgs -> BulkArgs := fun (b : Bytes) (rest : BulkArgs) => bulkMore b rest',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        f'def deleteScript : Script Reply {TAG} := do {{ r <- del Reply Hash {TAG} (jobs b"mail"); pure Reply {TAG} r }}']
    for entry, (name, values) in QUERY.items():
        cmd = command(name, values)
        if entry == 'computed':
            cmd = cmd.replace(arguments(values),
                f'(prepend (identity {tet(values[0])}) (keepArgs {arguments(values[1:])}))')
        next_step = (f'_ <- del Reply Hash {TAG} (jobs b"mail"); ' if entry == 'within' else
            f'view <- hgetall Reply {TAG} (jobs b"mail"); '
            if entry == 'snapshot' else '')
        result = 'r' if entry == 'raw' else 'view' if entry == 'snapshot' else 'expose r'
        declarations += [f'def {entry}Script : Script Reply {TAG} := do {{ r <- {cmd}; '
            f'{next_step}pure Reply {TAG} ({result}) }}',
            f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; done Reply r }}']
    declarations += [f'def earlier : Client Reply := do {{ r <- inv Reply {TAG} removeScript; '
        f'_ <- inv Reply {TAG} deleteScript; done Reply r }}']
    if seed is not None:
        entry, initial, *_ = cases()[seed]
        if isinstance(initial, dict):
            writes = [f'_ <- hset Reply {TAG} (jobs b"mail") {tet(field)} {tet(value)};' for field, value in sorted(initial.items())]
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
        require(not body.startswith(b'#!lua flags=no-writes\n'), 'HDEL-MANY write classification')
    return output


def twin(work, output, initial, expected, after, kind):
    try:
        support.lua(work, output, initial, wire(expected, kind) if kind == 'array' else expected, after, kind)
    except AssertionError as error:
        raise AssertionError('HDEL-MANY LuaJIT reply' if str(error) == 'LISTS LuaJIT reply' else str(error)) from None


def offline(work, outputs):
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        twin(work, outputs[entry], initial, expected, after, kind)
        seed = initial.decode() if isinstance(initial, bytes) else '@set' if isinstance(initial, set) else '@list' if isinstance(initial, list) else '@missing'
        (work / 'HdelManyCases.tet').write_text(source(i))
        rows = []
        code = support.checker.check(work, 'HdelManyCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
            'HdelManyCases.tet', 'seeded' if isinstance(initial, dict) else entry, KEY, seed, '1000000'], receive=rows.append)
        require(code == 0 and rows == [b'REPLY ' + wire(expected, kind) + b'\n'], f'HDEL-MANY store reply {i}: {rows!r}')
    print('PASS HDEL-MANY-ORACLES store=21 luajit=21', flush=True)


def refusals(work):
    invalid = []
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    for name in ('hdelMany',):
        cmd = command(name, [b'a'])
        invalid.append((cmd.replace(TAG, '(tag b"elsewhere")'), 'Hash', mismatch + b'(In SMu Tag [] (ACtor tag)'))
        invalid += [(cmd, schema, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode())
                    for schema, ctor in [('(Str Binary)', 'Str'), ('Set', 'Set'), ('List', 'List'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]]
        invalid += [(cmd.replace(arguments([b'a']), bad), 'Hash', b'CHECK unbound: ' + reason) for bad, reason in
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
        require(result.returncode == 2 and diagnostic in result.stderr, f'HDEL-MANY refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'HDEL-MANY refusal published output {i}')
    require(len(invalid) == 10, 'HDEL-MANY refusal inventory')
    print('PASS HDEL-MANY-REFUSALS cases=10 atomic_output=10', flush=True)


def live(work, outputs):
    hosts = rejected = errors = 0
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        live_cases = cases() + [(entry, kind, WRONG, kind, 'status')
                                for entry in ('remove',) for kind in ('zset', 'stream')]
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
                require(run(args, env=env, code=code) == wanted, f'HDEL-MANY {host} {entry} reply')
                if isinstance(after, dict):
                    check = ('local got=redis.call("HGETALL",KEYS[1]); local want=' + support.lua_fields(after)
                             + f'; if #got ~= {len(after) * 2} then return 0 end; '
                             + 'for i=1,#got,2 do if want[got[i]] ~= got[i+1] then return 0 end end; return 1')
                    require(run(redis + ['EVAL', check, '1', KEY]) == b'1\n', 'HDEL-MANY live complete hash')
                    require(run(redis + ['PEXPIRETIME', KEY]) == deadline, 'HDEL-MANY preserves expiry')
                elif after is None:
                    require(run(redis + ['EXISTS', KEY]) == b'0\n',
                            'HDEL-MANY retained reply survives deletion' if entry in ('within', 'earlier')
                            else 'HDEL-MANY removal deletes the key')
                else:
                    require(run(redis + ['DUMP', KEY]) == before and run(redis + ['PEXPIRETIME', KEY]) == deadline,
                            'HDEL-MANY wrong type preserves complete state')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'HDEL-MANY unrelated key')
                hosts, rejected = hosts + 1, rejected + int(code != 0)
        for entry in ('raw',):
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', KEY, 'wrong'])
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                require(run(args, env=env, code=4) == b'', 'HDEL-MANY error stops host')
                require(run(redis + ['GET', KEY]) == b'wrong\n', 'HDEL-MANY error preserves value')
                hosts, errors = hosts + 1, errors + 1
    require((hosts, rejected, errors) == (48, 2, 2), 'HDEL-MANY host inventory')
    print(f'PASS HDEL-MANY-E2E cases={len(live_cases)} hosts={hosts} utf8_refusals={rejected} errors={errors}', flush=True)
    count = 0
    for entry, expected in EXAMPLES.items():
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/ProfileCleanup.tet', '--entry', entry, '--host', host]) == expected,
                    f'HDEL-MANY example {entry} {host}')
            count += 1
    print(f'PASS HDEL-MANY-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline']), 'Usage: hdel-many-tests.py [--static|--offline|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-hdel-many-') as temporary:
        work = Path(temporary)
        path = work / 'HdelManyCases.tet'
        path.write_text(source())
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(entry in ENTRIES and bool(rows), 'HDEL-MANY probe must have cases')
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                twin(work, output, initial, expected, after, kind)
            print(f'PASS HDEL-MANY-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, path, entry) for entry in ENTRIES}
        print(f'PASS HDEL-MANY-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES.items():
            require(run(['./tether', 'run', 'examples/ProfileCleanup.tet', '--entry', entry]) == expected, 'HDEL-MANY interpreter example')
        if '--static' not in sys.argv:
            offline(work, outputs)
        if not sys.argv[1:]:
            live(work, outputs)
    print('PASS HDEL-MANY-TESTS' + (f' mode={sys.argv[1][2:]}' if sys.argv[1:] else ''), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL HDEL-MANY-TESTS {error}', file=sys.stderr)
        sys.exit(1)
