#!/usr/bin/env python3
"""SMEMBERS ordering, typed arrays, state preservation and host parity."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('set_members_support', ROOT / 'dev/list-range-tests.py')
arrays = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arrays)
support = arrays.support
run, require, tet = support.run, support.require, support.tet
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
READONLY = {'allScript', 'headScript', 'rawScript'}
ENTRIES = ('all', 'head', 'earlier', 'within', 'branch', 'raw')
EXAMPLE = b'["alice","bob"]\n'


def command():
    return f'smembers Reply {TAG} (jobs b"mail")'


def cases():
    rows = [('all', None, [], None, 'array')]
    for members in ({b'z', b'a', b'aa', b'a\0', b'\0', b''},
                    {b'10', b'2', b'01', b'9007199254740993'},
                    {support.TEXT, 'café'.encode(), b'plain'},
                    {b'"\n', b'$(touch forbidden)', b'\\', b''},
                    {bytes([i]) for i in range(256)},
                    {f'm{i:03}'.encode() for i in range(129)}):
        rows.append(('all', members, sorted(members), members, 'array'))
    rows += [('all', initial, WRONG, initial, 'status') for initial in (b'wrong', {b'f': b'v'}, [b'm'])]
    rows += [('head', {b'a', b'b'}, b'a', {b'a', b'b'}, 'bulk'),
             ('head', {b''}, b'', {b''}, 'bulk'), ('head', None, None, None, 'null'),
             ('earlier', {b'a', b'b'}, [b'a', b'b'], {b'b'}, 'array'),
             ('within', {b'a', b'b'}, [b'a', b'b'], {b'b'}, 'array'),
             ('branch', {b'a', b'b'}, [b'a', b'b'], {b'a', b'b'}, 'array')]
    require(len(rows) == 16, 'SET-MEMBERS case inventory')
    return rows


def source():
    declarations = ['module SetMembersCases', 'schema jobs : String -> Key Set tag b"queue"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        'def first : Replies -> Reply := fun (rs : Replies) => case rs as x in Replies return Reply with',
        '| repliesNil => nil | repliesCons r rest => r',
        'def headReply : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => first rs']
    for name, result in [('all', 'expose r'), ('head', 'headReply r'), ('raw', 'r')]:
        declarations += [f'def {name}Script : Script Reply {TAG} := do {{ r <- {command()}; pure Reply {TAG} ({result}) }}']
    declarations += [f'def removeScript : Script Reply {TAG} := do {{ '
        f'r <- srem Reply {TAG} (jobs b"mail") b"a"; pure Reply {TAG} r }}',
        f'def earlier : Client Reply := do {{ r <- inv Reply {TAG} allScript; '
        f'_ <- inv Reply {TAG} removeScript; done Reply r }}',
        f'def withinScript : Script Reply {TAG} := do {{ r <- {command()}; '
        f'_ <- srem Reply {TAG} (jobs b"mail") b"a"; pure Reply {TAG} r }}',
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
        if isinstance(initial, set):
            seeds = ' '.join(f'_ <- sadd Reply {TAG} (jobs b"mail") {tet(v)};' for v in sorted(initial))
            declarations += [f'def seed{i} : Script Reply {TAG} := do {{ {seeds} pure Reply {TAG} nil }}',
                f'def case{i} : Client Reply := do {{ _ <- inv Reply {TAG} seed{i}; {entry} }}']
    return '\n'.join(declarations) + '\n'


def emit(work, path, entry):
    output = work / entry
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'SET-MEMBERS canonical bodies')
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(body.startswith(b'#!lua flags=no-writes\n') == (script['entry'] in READONLY),
                'SET-MEMBERS write classification')
    return output


def twin(work, output, initial, expected, after, kind):
    ordered = kind == 'array' and isinstance(expected, list) and len(expected) > 1
    try:
        support.lua(work, output, initial, arrays.wire(expected, kind), after, kind)
    except AssertionError as error:
        reason = 'SET-MEMBERS LuaJIT member order' if ordered else 'SET-MEMBERS LuaJIT reply'
        require(False, f'{reason}: {error}')


def offline(work, outputs):
    stores = twins = 0
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        twin(work, outputs[entry], initial, expected, after, kind)
        twins += 1
        seed = (initial.decode() if isinstance(initial, bytes) else '@hash' if isinstance(initial, dict)
                else '@list' if isinstance(initial, list) else '@missing')
        rows = []
        code = support.checker.check(work, 'SetMembersCases.tet',
            command=[str(ROOT / '_build/default/dev/store_run.exe'), 'SetMembersCases.tet',
                     f'case{i}' if isinstance(initial, set) else entry, KEY, seed, '1000000'], receive=rows.append)
        encoded = (arrays.wire(expected, kind) if kind == 'array' else b'null' if kind == 'null'
                   else kind.encode() + b':' + expected.hex().encode())
        require(code == 0 and rows == [b'REPLY ' + encoded + b'\n'], f'SET-MEMBERS store reply {i}: {rows!r}')
        stores += 1
    print(f'PASS SET-MEMBERS-ORACLES store={stores} luajit={twins}', flush=True)


def refusals(work):
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = [(command().replace(TAG, '(tag b"elsewhere")'), 'Set', mismatch + b'(In SMu Tag [] (ACtor tag)')]
    invalid += [(command(), schema, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode())
                for schema, ctor in [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('List', 'List'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]]
    for i, (cmd, schema, diagnostic) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{i}'
        path.write_text(f'module Refused\nschema jobs : String -> Key {schema} tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ r <- {cmd}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'SET-MEMBERS refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'SET-MEMBERS refusal published output {i}')
    print(f'PASS SET-MEMBERS-REFUSALS cases={len(invalid)} atomic_output={len(invalid)}', flush=True)


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
                    for field, value in initial.items():
                        run(redis + ['HSET', KEY, field, value])
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
                require(run(args, env=env, code=code) == wanted, f'SET-MEMBERS {host} {entry} reply')
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                if after == initial:
                    require(run(redis + ['DUMP', KEY]) == before, 'SET-MEMBERS preserved complete value')
                else:
                    require(isinstance(after, set) and run(redis + ['TYPE', KEY]) == b'set\n', 'SET-MEMBERS updated type')
                    require(run(redis + ['SCARD', KEY]) == str(len(after)).encode() + b'\n', 'SET-MEMBERS updated count')
                    for value in after:
                        require(run(redis + ['SISMEMBER', KEY, value]) == b'1\n', 'SET-MEMBERS updated membership')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'SET-MEMBERS unrelated key')
                hosts, readonly, rejected = hosts + 1, readonly + int(ro), rejected + int(code != 0)
        run(redis + ['FLUSHDB'])
        run(redis + ['SET', KEY, 'wrong'])
        run(redis + ['ACL', 'SETUSER', 'default', '-eval', '-evalsha'])
        output = outputs['raw']
        for args in (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)], ['/bin/bash', str(output / 'prog.sh')]):
            require(run(args, env=env, code=4) == b'', 'SET-MEMBERS error stops host')
            require(run(redis + ['GET', KEY]) == b'wrong\n', 'SET-MEMBERS error preserves key')
            hosts, readonly, errors = hosts + 1, readonly + 1, errors + 1
        require((hosts, readonly, rejected, errors) == (38, 32, 2, 2), 'SET-MEMBERS host inventory')
        print(f'PASS SET-MEMBERS-E2E cases={len(live_cases)} hosts={hosts} readonly={readonly} '
              f'utf8_refusals={rejected} errors={errors}', flush=True)
    count = 0
    for entry in ('main', 'retained'):
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/TeamRoster.tet', '--entry', entry, '--host', host]) == EXAMPLE,
                    f'SET-MEMBERS example {entry} {host}')
            count += 1
    print(f'PASS SET-MEMBERS-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline'], ['--artifacts']),
            'Usage: set-members-tests.py [--static|--offline|--artifacts|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-set-members-') as temporary:
        work = Path(temporary)
        path = work / 'SetMembersCases.tet'
        path.write_text(source())
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(bool(rows), 'SET-MEMBERS unknown or empty probe')
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                twin(work, output, initial, expected, after, kind)
            print(f'PASS SET-MEMBERS-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, path, entry) for entry in ENTRIES}
        print(f'PASS SET-MEMBERS-ARTIFACTS pairs={len(outputs)}', flush=True)
        if '--artifacts' not in sys.argv:
            refusals(work)
            for entry in ('main', 'retained'):
                require(run(['./tether', 'run', 'examples/TeamRoster.tet', '--entry', entry]) == EXAMPLE, 'SET-MEMBERS interpreter example')
            if '--static' not in sys.argv:
                offline(work, outputs)
            if not sys.argv[1:]:
                live(work, outputs)
    mode = f" mode={sys.argv[1].lstrip('-')}" if sys.argv[1:] else ''
    print(f'PASS SET-MEMBERS-TESTS{mode}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL SET-MEMBERS-TESTS {error}', file=sys.stderr)
        sys.exit(1)
