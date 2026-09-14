#!/usr/bin/env python3
"""HGETALL ordering, typed arrays, state preservation and host parity."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hash_entries_support', ROOT / 'dev/list-range-tests.py')
arrays = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arrays)
support = arrays.support
run, require, tet = support.run, support.require, support.tet
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
READONLY = {'allScript', 'headScript', 'valueScript', 'rawScript'}
ENTRIES = ('all', 'head', 'value', 'earlier', 'within', 'branch', 'raw')
EXAMPLE = b'["name","Alice","visits","9007199254740993"]\n'


def command():
    return f'hgetall Reply {TAG} (jobs b"mail")'


def cases():
    rows = [('all', None, [], None, 'array')]
    for fields in ({b'z': b'A', b'a': b'Z', b'aa': b'a', b'a\0': b'prefix', b'\0': b'zero', b'': b'empty'},
                   {b'10': b'z', b'2': b'a', b'01': b'1', b'number': b'9007199254740993'},
                   {'café'.encode(): support.TEXT, b'plain': 'été'.encode()},
                   {b'"\n': b'$(touch forbidden)', b'\\': b'', b'': b'\0\n'},
                   {bytes([i]): b'v' for i in range(256)},
                   {b'raw': bytes(range(256))},
                   {f'f{i:03}'.encode(): f'v{128-i:03}'.encode() for i in range(129)}):
        flat = [part for field, value in sorted(fields.items()) for part in (field, value)]
        rows.append(('all', fields, flat, fields, 'array'))
    rows += [('all', initial, WRONG, initial, 'status') for initial in (b'wrong', [b'm'], {b'm'})]
    initial = {b'a': b'1', b'b': b'2'}
    rows += [('head', {b'a': b'z', b'b': b'y'}, b'a', {b'a': b'z', b'b': b'y'}, 'bulk'),
             ('head', {b'': b'v'}, b'', {b'': b'v'}, 'bulk'), ('head', None, None, None, 'null'),
             ('value', {b'a': b'z'}, b'z', {b'a': b'z'}, 'bulk'),
             ('value', {b'a': b''}, b'', {b'a': b''}, 'bulk'),
             ('earlier', initial, [b'a', b'1', b'b', b'2'], {b'b': b'2'}, 'array'),
             ('within', initial, [b'a', b'1', b'b', b'2'], {b'b': b'2'}, 'array'),
             ('branch', initial, [b'a', b'1', b'b', b'2'], initial, 'array')]
    require(len(rows) == 19, 'HASH-ENTRIES case inventory')
    return rows


def source():
    declarations = ['module HashEntriesCases', 'schema jobs : String -> Key Hash tag b"queue"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        'def first : Replies -> Reply := fun (rs : Replies) => case rs as x in Replies return Reply with',
        '| repliesNil => nil | repliesCons r rest => r',
        'def second : Replies -> Reply := fun (rs : Replies) => case rs as x in Replies return Reply with',
        '| repliesNil => nil | repliesCons r rest => first rest',
        'def valueReply : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => second rs',
        'def headReply : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => first rs']
    for name, result in [('all', 'expose r'), ('head', 'headReply r'), ('value', 'valueReply r'), ('raw', 'r')]:
        declarations += [f'def {name}Script : Script Reply {TAG} := do {{ r <- {command()}; pure Reply {TAG} ({result}) }}']
    declarations += [f'def removeScript : Script Reply {TAG} := do {{ '
        f'r <- hdel Reply {TAG} (jobs b"mail") b"a"; pure Reply {TAG} r }}',
        f'def earlier : Client Reply := do {{ r <- inv Reply {TAG} allScript; '
        f'_ <- inv Reply {TAG} removeScript; done Reply r }}',
        f'def withinScript : Script Reply {TAG} := do {{ r <- {command()}; '
        f'_ <- hdel Reply {TAG} (jobs b"mail") b"a"; pure Reply {TAG} r }}',
        f'def choose : Reply -> Script Reply {TAG} := fun (r : Reply) =>',
        f'case r as x in Reply return Script Reply {TAG} with',
        f'| nil => pure Reply {TAG} nil | int n => removeScript',
        f'| bulk b => pure Reply {TAG} (bulk b) | status b => pure Reply {TAG} (status b)',
        f'| err b => pure Reply {TAG} (err b) | array rs => pure Reply {TAG} (array rs)',
        f'def branchScript : Script Reply {TAG} := do {{ r <- {command()}; choose r }}']
    for name in ENTRIES:
        if name != 'earlier':
            declarations += [f'def {name} : Client Reply := do {{ r <- inv Reply {TAG} {name}Script; done Reply r }}']
    for i, (entry, initial, *_rest) in enumerate(cases()):
        if isinstance(initial, dict):
            seeds = ' '.join(f'_ <- hset Reply {TAG} (jobs b"mail") {tet(f)} {tet(v)};' for f, v in reversed(sorted(initial.items())))
            declarations += [f'def seed{i} : Script Reply {TAG} := do {{ {seeds} pure Reply {TAG} nil }}',
                f'def case{i} : Client Reply := do {{ _ <- inv Reply {TAG} seed{i}; {entry} }}']
    return '\n'.join(declarations) + '\n'


def emit(work, path, entry):
    output = work / entry
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'HASH-ENTRIES canonical bodies')
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(body.startswith(b'#!lua flags=no-writes\n') == (script['entry'] in READONLY),
                'HASH-ENTRIES write classification')
    return output


def twin(work, output, initial, expected, after, kind):
    ordered = kind == 'array' and isinstance(expected, list) and len(expected) > 1
    try:
        support.lua(work, output, initial, arrays.wire(expected, kind), after, kind)
    except AssertionError as error:
        reason = 'HASH-ENTRIES LuaJIT field/value order' if ordered else 'HASH-ENTRIES LuaJIT reply'
        require(False, f'{reason}: {error}')


def offline(work, outputs):
    stores = twins = 0
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        twin(work, outputs[entry], initial, expected, after, kind)
        twins += 1
        seed = (initial.decode() if isinstance(initial, bytes) else '@set' if isinstance(initial, set)
                else '@list' if isinstance(initial, list) else '@missing')
        rows = []
        code = support.checker.check(work, 'HashEntriesCases.tet',
            command=[str(ROOT / '_build/default/dev/store_run.exe'), 'HashEntriesCases.tet',
                     f'case{i}' if isinstance(initial, dict) else entry, KEY, seed, '1000000'], receive=rows.append)
        encoded = (arrays.wire(expected, kind) if kind == 'array' else b'null' if kind == 'null'
                   else kind.encode() + b':' + expected.hex().encode())
        require(code == 0 and rows == [b'REPLY ' + encoded + b'\n'], f'HASH-ENTRIES store reply {i}: {rows!r}')
        stores += 1
    print(f'PASS HASH-ENTRIES-ORACLES store={stores} luajit={twins}', flush=True)


def refusals(work):
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = [(command().replace(TAG, '(tag b"elsewhere")'), 'Hash', mismatch + b'(In SMu Tag [] (ACtor tag)')]
    invalid += [(command(), schema, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode())
                for schema, ctor in [('(Str Binary)', 'Str'), ('Set', 'Set'), ('List', 'List'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]]
    for i, (cmd, schema, diagnostic) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{i}'
        path.write_text(f'module Refused\nschema jobs : String -> Key {schema} tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ r <- {cmd}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'HASH-ENTRIES refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'HASH-ENTRIES refusal published output {i}')
    print(f'PASS HASH-ENTRIES-REFUSALS cases={len(invalid)} atomic_output={len(invalid)}', flush=True)


def live(work, outputs):
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        hosts = readonly = rejected = errors = 0
        live_cases = cases() + [('all', kind, WRONG, kind, 'status') for kind in ('zset', 'stream')]
        for entry, initial, expected, after, kind in live_cases:
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                if isinstance(initial, (set, list)):
                    operation = 'SADD' if isinstance(initial, set) else 'RPUSH'
                    seeds = list(reversed(sorted(initial))) if isinstance(initial, set) else list(initial)
                    for value in seeds:
                        run(redis + ['EVAL', f"return redis.call('{operation}',KEYS[1]," + support.literal(value) + ')', '1', KEY])
                elif isinstance(initial, dict):
                    for field, value in reversed(sorted(initial.items())):
                        script = "return redis.call('HSET',KEYS[1]," + support.literal(field) + ',' + support.literal(value) + ')'
                        run(redis + ['EVAL', script, '1', KEY])
                elif initial == 'zset':
                    run(redis + ['ZADD', KEY, '1', 'm'])
                elif initial == 'stream':
                    run(redis + ['XADD', KEY, '*', 'f', 'v'])
                elif initial is not None:
                    run(redis + ['-x', 'SET', KEY], data=initial)
                before = run(redis + ['DUMP', KEY])
                ro = entry + 'Script' in READONLY
                run(redis + ['ACL', 'SETUSER', 'default', '-eval' if ro else '+eval', '-evalsha' if ro else '+evalsha'])
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                try:
                    wanted, code = arrays.stdout(expected, kind), 0
                except UnicodeDecodeError:
                    wanted, code = b'', 4
                require(run(args, env=env, code=code) == wanted, f'HASH-ENTRIES {host} {entry} reply')
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                if after == initial:
                    require(run(redis + ['DUMP', KEY]) == before, 'HASH-ENTRIES preserved complete value')
                else:
                    require(isinstance(after, dict) and run(redis + ['TYPE', KEY]) == b'hash\n', 'HASH-ENTRIES updated type')
                    require(run(redis + ['HLEN', KEY]) == str(len(after)).encode() + b'\n', 'HASH-ENTRIES updated count')
                    for field, value in after.items():
                        require(run(redis + ['HGET', KEY, field]) == value + b'\n', 'HASH-ENTRIES updated field')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'HASH-ENTRIES unrelated key')
                hosts, readonly, rejected = hosts + 1, readonly + int(ro), rejected + int(code != 0)
        run(redis + ['FLUSHDB'])
        run(redis + ['SET', KEY, 'wrong'])
        run(redis + ['ACL', 'SETUSER', 'default', '-eval', '-evalsha'])
        output = outputs['raw']
        for args in (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)], ['/bin/bash', str(output / 'prog.sh')]):
            require(run(args, env=env, code=4) == b'', 'HASH-ENTRIES error stops host')
            require(run(redis + ['GET', KEY]) == b'wrong\n', 'HASH-ENTRIES error preserves key')
            hosts, readonly, errors = hosts + 1, readonly + 1, errors + 1
        require((hosts, readonly, rejected, errors) == (44, 38, 4, 2), 'HASH-ENTRIES host inventory')
        print(f'PASS HASH-ENTRIES-E2E cases={len(live_cases)} hosts={hosts} readonly={readonly} '
              f'utf8_refusals={rejected} errors={errors}', flush=True)
    count = 0
    for entry in ('main', 'retained'):
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/HashSnapshot.tet', '--entry', entry, '--host', host]) == EXAMPLE,
                    f'HASH-ENTRIES example {entry} {host}')
            count += 1
    print(f'PASS HASH-ENTRIES-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline'], ['--artifacts']),
            'Usage: hash-entries-tests.py [--static|--offline|--artifacts|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-hash-entries-') as temporary:
        work = Path(temporary)
        path = work / 'HashEntriesCases.tet'
        path.write_text(source())
        if probe:
            entry = sys.argv[2]
            require(entry in ENTRIES, 'HASH-ENTRIES unknown probe')
            rows = [row for row in cases() if row[0] == entry]
            require(bool(rows), f'HASH-ENTRIES entry {entry} has no LuaJIT cases')
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                twin(work, output, initial, expected, after, kind)
            print(f'PASS HASH-ENTRIES-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, path, entry) for entry in ENTRIES}
        print(f'PASS HASH-ENTRIES-ARTIFACTS pairs={len(outputs)}', flush=True)
        if '--artifacts' not in sys.argv:
            refusals(work)
            for entry in ('main', 'retained'):
                require(run(['./tether', 'run', 'examples/HashSnapshot.tet', '--entry', entry]) == EXAMPLE, 'HASH-ENTRIES interpreter example')
            if '--static' not in sys.argv:
                offline(work, outputs)
            if not sys.argv[1:]:
                live(work, outputs)
    mode = f" mode={sys.argv[1].lstrip('-')}" if sys.argv[1:] else ''
    print(f'PASS HASH-ENTRIES-TESTS{mode}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL HASH-ENTRIES-TESTS {error}', file=sys.stderr)
        sys.exit(1)
