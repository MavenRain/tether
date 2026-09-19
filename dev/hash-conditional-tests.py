#!/usr/bin/env python3
"""Conditional Hash writes and byte lengths against the store, twin and Redis."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hash_conditional_support', ROOT / 'dev/lists-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, tet, literal = support.run, support.require, support.tet, support.literal
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
BASE = f'Reply {TAG} (jobs b"mail")'
FIELD, BINARY = b'\x00\xff"\n$(touch forbidden)\\field', bytes(range(256))
QUERY = {
    'insert': f'hsetnx {BASE} b"f" b"new"',
    'insertEmpty': f'hsetnx {BASE} b"" b""',
    'insertBinary': f'hsetnx {BASE} {tet(FIELD)} {tet(BINARY)}',
    'computed': f'hsetnx {BASE} (identity b"f") (identity b"new")',
    'length': f'hstrlen {BASE} b"f"',
    'lengthEmpty': f'hstrlen {BASE} b""',
    'lengthBinary': f'hstrlen {BASE} {tet(FIELD)}',
    'within': f'hsetnx {BASE} b"f" b"new"',
    'lengthWithin': f'hstrlen {BASE} b"f"',
    'rawInsert': f'hsetnx {BASE} b"f" b"new"',
    'rawLength': f'hstrlen {BASE} b"f"',
}
ENTRIES = tuple(QUERY) + ('earlier', 'lengthEarlier')
READONLY = {'lengthScript', 'lengthEmptyScript', 'lengthBinaryScript', 'rawLengthScript'}
EXAMPLES = {'main': b'["name","Alice","role","member"]\n', 'length': b'5\n', 'retained': b'1\n'}


def cases():
    rows = [
        ('insert', None, b'1', {b'f': b'new'}, 'int'),
        ('insert', {b'other': b'kept'}, b'1', {b'f': b'new', b'other': b'kept'}, 'int'),
        ('insert', {b'f': b'old', b'other': b'kept'}, b'0', {b'f': b'old', b'other': b'kept'}, 'int'),
        ('insert', {b'f': b''}, b'0', {b'f': b''}, 'int'),
        ('insertEmpty', None, b'1', {b'': b''}, 'int'),
        ('insertEmpty', {b'': b''}, b'0', {b'': b''}, 'int'),
        ('insertEmpty', {b'other': b'kept'}, b'1', {b'': b'', b'other': b'kept'}, 'int'),
        ('insertBinary', None, b'1', {FIELD: BINARY}, 'int'),
        ('insertBinary', {b'\x00': b'kept'}, b'1', {FIELD: BINARY, b'\x00': b'kept'}, 'int'),
        ('insertBinary', {FIELD: b''}, b'0', {FIELD: b''}, 'int'),
        ('computed', {b'other': b'kept'}, b'1', {b'f': b'new', b'other': b'kept'}, 'int'),
        ('computed', {b'f': b''}, b'0', {b'f': b''}, 'int'),
        ('length', None, b'0', None, 'int'),
        ('length', {b'other': b'kept'}, b'0', {b'other': b'kept'}, 'int'),
        ('length', {b'f': b''}, b'0', {b'f': b''}, 'int'),
        ('length', {b'f': b'hello'}, b'5', {b'f': b'hello'}, 'int'),
        ('length', {b'f': 'é🙂'.encode()}, b'6', {b'f': 'é🙂'.encode()}, 'int'),
        ('length', {b'f': BINARY}, b'256', {b'f': BINARY}, 'int'),
        ('lengthEmpty', None, b'0', None, 'int'),
        ('lengthEmpty', {b'': b'abc'}, b'3', {b'': b'abc'}, 'int'),
        ('lengthBinary', {FIELD: BINARY}, b'256', {FIELD: BINARY}, 'int'),
        ('within', {b'f': b'old'}, b'0', None, 'int'),
        ('within', None, b'1', None, 'int'),
        ('earlier', {b'f': b'old'}, b'0', None, 'int'),
        ('lengthWithin', {b'f': 'é🙂'.encode()}, b'6', None, 'int'),
        ('lengthEarlier', {b'f': b'abc'}, b'3', None, 'int'),
        ('rawInsert', None, b'1', {b'f': b'new'}, 'int'),
        ('rawLength', {b'f': b'new'}, b'3', {b'f': b'new'}, 'int'),
    ]
    rows += [(entry, value, WRONG, value, 'status')
             for entry in ('insert', 'length') for value in (b'wrong', {b'm'}, [b'm'])]
    require(len(rows) == 34, 'HASH-CONDITIONAL case inventory')
    return rows


def source(seed=None):
    declarations = ['module HashConditionalCases', 'schema jobs : String -> Key Hash tag b"queue"',
        'def identity : Bytes -> Bytes := fun (b : Bytes) => b',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        f'def deleteScript : Script Reply {TAG} := do {{ r <- del Reply Hash {TAG} (jobs b"mail"); pure Reply {TAG} r }}']
    for entry, command in QUERY.items():
        remove = f'_ <- del Reply Hash {TAG} (jobs b"mail"); ' if entry in ('within', 'lengthWithin') else ''
        answer = 'r' if entry in ('rawInsert', 'rawLength') else 'expose r'
        declarations += [f'def {entry}Script : Script Reply {TAG} := do {{ r <- {command}; '
            f'{remove}pure Reply {TAG} ({answer}) }}',
            f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; done Reply r }}']
    for entry, first in [('earlier', 'insert'), ('lengthEarlier', 'length')]:
        declarations += [f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {first}Script; '
            f'_ <- inv Reply {TAG} deleteScript; done Reply r }}']
    if seed is not None:
        entry, initial, *_ = cases()[seed]
        if isinstance(initial, dict):
            writes = [f'_ <- hset Reply {TAG} (jobs b"mail") {tet(f)} {tet(v)};' for f, v in sorted(initial.items())]
            declarations += [f'def seedScript : Script Reply {TAG} := do {{ ' + ' '.join(writes)
                + f' pure Reply {TAG} (status b"OK") }}',
                f'def seeded : Client Reply := do {{ _ <- inv Reply {TAG} seedScript; {entry} }}']
    return '\n'.join(declarations) + '\n'


def emit(work, path, entry):
    output = work / ('out-' + entry)
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'HASH-CONDITIONAL canonical bodies')
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(body.startswith(b'#!lua flags=no-writes\n') == (script['entry'] in READONLY), 'HASH-CONDITIONAL write classification')
    return output


def twin(work, output, initial, expected, after, kind):
    scripts = {s['entry']: s for s in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = ['{path=' + literal(output / (scripts[name]['stem'] + '.lua')) + ',keys={' +
             ','.join(literal(k) for k in scripts[name]['keys']) + '}}' for name in plan['invokes']]
    value = support.lua_fields(initial) if isinstance(initial, dict) else literal(initial) if isinstance(initial, bytes) else 'nil'
    binding = '[' + literal(KEY) + ']='
    lists = '{' + binding + support.lua_items(initial) + '}' if isinstance(initial, list) else '{}'
    sets = '{' + binding + support.lua_members(initial) + '}' if isinstance(initial, set) else '{}'
    check = ('kind="hash",fields=' + support.lua_fields(after) if isinstance(after, dict)
             else 'kind="list",items=' + support.lua_items(after) if isinstance(after, list)
             else 'kind="set",members=' + support.lua_members(after) if isinstance(after, set)
             else 'value=' + ('false' if after is None else literal(after)))
    deadline = binding + '"7000"' if initial is not None else ''
    expiry = 'false' if initial is None or after is None else '"7000"'
    config = work / 'hash-conditional-config.lua'
    config.write_text('return {values={other="kept",' + binding + value + '},lists=' + lists + ',sets=' + sets +
        ',now="1000",deadlines={other="9000",' + deadline + '},expiries={other="9000",' + binding + expiry +
        '},invokes={' + ','.join(calls) + '},answer=' + str(plan['answer']) + ',kind=' +
        literal('status' if kind == 'status' else 'string') + ',checks={{key=' + literal(KEY) + ',' + check +
        '},{key="other",value="kept"}}}\n')
    require(run(['luajit', '-joff', 'dev/lua-store.lua', str(config)]) == expected + b'\n', 'HASH-CONDITIONAL LuaJIT reply')


def offline(work, outputs):
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        twin(work, outputs[entry], initial, expected, after, kind)
        seed = initial.decode() if isinstance(initial, bytes) else '@set' if isinstance(initial, set) else '@list' if isinstance(initial, list) else '@missing'
        (work / 'HashConditionalCases.tet').write_text(source(i))
        rows = []
        code = support.checker.check(work, 'HashConditionalCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
            'HashConditionalCases.tet', 'seeded' if isinstance(initial, dict) else entry, KEY, seed, '1000000'], receive=rows.append)
        require(code == 0 and rows == [b'REPLY ' + kind.encode() + b':' + expected.hex().encode() + b'\n'], f'HASH-CONDITIONAL store reply {i}: {rows!r}')
    print('PASS HASH-CONDITIONAL-ORACLES store=34 luajit=34', flush=True)


def refusals(work):
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = []
    for entry in ('insert', 'length'):
        command = QUERY[entry]
        invalid += [(command.replace(TAG, '(tag b"elsewhere")'), 'Hash', mismatch + b'(In SMu Tag [] (ACtor tag)')]
        invalid += [(command, schema, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode())
                    for schema, ctor in [('(Str Binary)', 'Str'), ('Set', 'Set'), ('List', 'List'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]]
        invalid += [(command.replace('b"f"', 'nil'), 'Hash', b'CHECK unbound: nil is not a constructor of Bytes')]
    invalid += [(QUERY['insert'].replace('b"new"', 'nil'), 'Hash', b'CHECK unbound: nil is not a constructor of Bytes')]
    for i, (body, schema, diagnostic) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{i}'
        path.write_text(f'module Refused\nschema jobs : String -> Key {schema} tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ r <- {body}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'HASH-CONDITIONAL refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'HASH-CONDITIONAL refusal published output {i}')
    require(len(invalid) == 15, 'HASH-CONDITIONAL refusal inventory')
    print('PASS HASH-CONDITIONAL-REFUSALS cases=15 atomic_output=15', flush=True)


def live(work, outputs):
    hosts = errors = 0
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        live_cases = cases() + [(entry, kind, WRONG, kind, 'status')
            for entry in ('insert', 'length') for kind in ('zset', 'stream')]
        for entry, initial, expected, after, _kind in live_cases:
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                if isinstance(initial, (set, list)):
                    operation = 'SADD' if isinstance(initial, set) else 'RPUSH'
                    for value in initial:
                        run(redis + ['EVAL', f"return redis.call('{operation}',KEYS[1]," + literal(value) + ')', '1', KEY])
                elif isinstance(initial, dict):
                    for field, value in initial.items():
                        run(redis + ['EVAL', "return redis.call('HSET',KEYS[1]," + literal(field) + ',' + literal(value) + ')', '1', KEY])
                elif initial == 'zset':
                    run(redis + ['ZADD', KEY, '1', 'm'])
                elif initial == 'stream':
                    run(redis + ['XADD', KEY, '*', 'f', 'v'])
                elif initial is not None:
                    run(redis + ['-x', 'SET', KEY], data=initial)
                run(redis + ['PEXPIREAT', KEY, '4102444800000'])
                before, deadline = run(redis + ['DUMP', KEY]), run(redis + ['PEXPIRETIME', KEY])
                output = outputs[entry]
                args = ['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)] if host == 'node' else ['/bin/bash', str(output / 'prog.sh')]
                require(run(args, env=env) == expected + b'\n', f'HASH-CONDITIONAL {host} {entry} reply')
                if isinstance(after, dict):
                    check = ('local got=redis.call("HGETALL",KEYS[1]); local want=' + support.lua_fields(after)
                        + f'; if #got ~= {len(after) * 2} then return 0 end; '
                        + 'for i=1,#got,2 do if want[got[i]] ~= got[i+1] then return 0 end end; return 1')
                    require(run(redis + ['EVAL', check, '1', KEY]) == b'1\n', 'HASH-CONDITIONAL live complete hash')
                    require(run(redis + ['PEXPIRETIME', KEY]) == (b'-1\n' if initial is None else deadline), 'HASH-CONDITIONAL preserves expiry')
                elif after is None:
                    require(run(redis + ['EXISTS', KEY]) == b'0\n', 'HASH-CONDITIONAL absent key')
                else:
                    require(run(redis + ['DUMP', KEY]) == before and run(redis + ['PEXPIRETIME', KEY]) == deadline,
                            'HASH-CONDITIONAL wrong type preserves complete state')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'HASH-CONDITIONAL unrelated key')
                hosts += 1
        for entry in ('rawInsert', 'rawLength'):
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', KEY, 'wrong'])
                output = outputs[entry]
                args = ['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)] if host == 'node' else ['/bin/bash', str(output / 'prog.sh')]
                require(run(args, env=env, code=4) == b'', 'HASH-CONDITIONAL error stops host')
                require(run(redis + ['GET', KEY]) == b'wrong\n', 'HASH-CONDITIONAL error preserves value')
                hosts, errors = hosts + 1, errors + 1
    require((hosts, errors) == (80, 4), 'HASH-CONDITIONAL host inventory')
    print(f'PASS HASH-CONDITIONAL-E2E cases={len(live_cases)} hosts={hosts} errors={errors}', flush=True)
    count = 0
    for entry, expected in EXAMPLES.items():
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/ProfileDefaults.tet', '--entry', entry, '--host', host]) == expected,
                    f'HASH-CONDITIONAL example {entry} {host}')
            count += 1
    print(f'PASS HASH-CONDITIONAL-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline']), 'Usage: hash-conditional-tests.py [--static|--offline|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-hash-conditional-') as temporary:
        work = Path(temporary)
        path = work / 'HashConditionalCases.tet'
        path.write_text(source())
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(entry in ENTRIES and bool(rows), 'HASH-CONDITIONAL probe must have cases')
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                twin(work, output, initial, expected, after, kind)
            print(f'PASS HASH-CONDITIONAL-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, path, entry) for entry in ENTRIES}
        print(f'PASS HASH-CONDITIONAL-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES.items():
            require(run(['./tether', 'run', 'examples/ProfileDefaults.tet', '--entry', entry]) == expected, 'HASH-CONDITIONAL interpreter example')
        if '--static' not in sys.argv:
            offline(work, outputs)
        if not sys.argv[1:]:
            live(work, outputs)
    print('PASS HASH-CONDITIONAL-TESTS' + (f' mode={sys.argv[1][2:]}' if sys.argv[1:] else ''), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL HASH-CONDITIONAL-TESTS {error}', file=sys.stderr)
        sys.exit(1)
