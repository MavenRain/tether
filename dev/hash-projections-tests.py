#!/usr/bin/env python3
"""Hash projections, sorted byte replies, retained arrays and host parity."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hash_projections_support', ROOT / 'dev/list-range-tests.py')
arrays = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arrays)
support = arrays.support
run, require, tet = support.run, support.require, support.tet
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
KINDS = ('keys', 'vals')
ENTRIES = tuple(kind + suffix for kind in KINDS for suffix in ('', 'Head', 'Earlier', 'Within', 'Branch', 'Raw'))
READONLY = {kind + suffix + 'Script' for kind in KINDS for suffix in ('', 'Head', 'Raw')}
EXAMPLES = {'main': b'["name","plan","role"]\n', 'retained': b'["Alice","member","member"]\n'}


def command(kind):
    return f'h{kind} Reply {TAG} (jobs b"mail")'


def project(kind, fields):
    return sorted(fields.keys() if kind == 'keys' else fields.values())


def cases():
    rows = []
    for kind in KINDS:
        rows.append((kind, None, [], None, 'array'))
        for fields in ({b'z': b'A', b'a': b'Z', b'aa': b'a', b'a\0': b'prefix', b'\0': b'zero', b'': b'empty'},
                       {b'10': b'z', b'2': b'a', b'01': b'1', b'number': b'9007199254740993'},
                       {'café'.encode(): support.TEXT, b'plain': 'été'.encode()},
                       {b'"\n': b'$(touch forbidden)', b'\\': b'', b'': b'\0\n'},
                       {bytes([i]): b'v' for i in range(256)},
                       {b'raw': bytes(range(256))},
                       {f'f{i:03}'.encode(): f'v{128-i:03}'.encode() for i in range(129)},
                       {b'z': b'x', b'a': b'x', b'b': b'y'},
                       {f'f{i:03}'.encode(): bytes([255-i]) for i in range(256)}):
            rows.append((kind, fields, project(kind, fields), fields, 'array'))
        rows += [(kind, initial, WRONG, initial, 'status') for initial in (b'wrong', [b'm'], {b'm'})]
        initial = {b'a': b'2', b'b': b'1'}
        rows += [(kind + 'Head', {b'a': b'z', b'b': b'y'}, b'a' if kind == 'keys' else b'y', {b'a': b'z', b'b': b'y'}, 'bulk'),
                 (kind + 'Head', {b'': b''}, b'', {b'': b''}, 'bulk'), (kind + 'Head', None, None, None, 'null'),
                 (kind + 'Earlier', initial, project(kind, initial), {b'b': b'1'}, 'array'),
                 (kind + 'Within', initial, project(kind, initial), {b'b': b'1'}, 'array'),
                 (kind + 'Branch', initial, project(kind, initial), initial, 'array')]
    require(len(rows) == 38, 'HASH-PROJECTIONS case inventory')
    return rows


def source(seed=None):
    declarations = ['module HashProjectionsCases', 'schema jobs : String -> Key Hash tag b"queue"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        'def first : Replies -> Reply := fun (rs : Replies) => case rs as x in Replies return Reply with',
        '| repliesNil => nil | repliesCons r rest => r',
        'def headReply : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => first rs',
        f'def removeScript : Script Reply {TAG} := do {{ '
        f'r <- hdel Reply {TAG} (jobs b"mail") b"a"; pure Reply {TAG} r }}',
        f'def choose : Reply -> Script Reply {TAG} := fun (r : Reply) =>',
        f'case r as x in Reply return Script Reply {TAG} with',
        f'| nil => pure Reply {TAG} nil | int n => removeScript',
        f'| bulk b => pure Reply {TAG} (bulk b) | status b => pure Reply {TAG} (status b)',
        f'| err b => pure Reply {TAG} (err b) | array rs => pure Reply {TAG} (array rs)']
    for kind in KINDS:
        for suffix, result in [('', 'expose r'), ('Head', 'headReply r'), ('Raw', 'r')]:
            declarations += [f'def {kind}{suffix}Script : Script Reply {TAG} := do {{ r <- {command(kind)}; pure Reply {TAG} ({result}) }}']
        declarations += [f'def {kind}Earlier : Client Reply := do {{ r <- inv Reply {TAG} {kind}Script; '
            f'_ <- inv Reply {TAG} removeScript; done Reply r }}',
            f'def {kind}WithinScript : Script Reply {TAG} := do {{ r <- {command(kind)}; '
            f'_ <- hdel Reply {TAG} (jobs b"mail") b"a"; pure Reply {TAG} r }}',
            f'def {kind}BranchScript : Script Reply {TAG} := do {{ r <- {command(kind)}; choose r }}']
    for name in ENTRIES:
        if not name.endswith('Earlier'):
            declarations += [f'def {name} : Client Reply := do {{ r <- inv Reply {TAG} {name}Script; done Reply r }}']
    for i, (entry, initial, *_rest) in enumerate(cases()):
        if i == seed and isinstance(initial, dict):
            seeds = ' '.join(f'_ <- hset Reply {TAG} (jobs b"mail") {tet(f)} {tet(v)};' for f, v in reversed(sorted(initial.items())))
            declarations += [f'def seed{i} : Script Reply {TAG} := do {{ {seeds} pure Reply {TAG} nil }}',
                f'def case{i} : Client Reply := do {{ _ <- inv Reply {TAG} seed{i}; {entry} }}']
    return '\n'.join(declarations) + '\n'


def emit(work, path, entry):
    output = work / entry
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'HASH-PROJECTIONS canonical bodies')
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(body.startswith(b'#!lua flags=no-writes\n') == (script['entry'] in READONLY),
                'HASH-PROJECTIONS write classification')
    return output


def twin(work, output, initial, expected, after, kind):
    try:
        support.lua(work, output, initial, arrays.wire(expected, kind), after, kind)
    except AssertionError as error:
        require(False, f'HASH-PROJECTIONS LuaJIT reply: {error}')


def offline(work, outputs):
    stores = twins = 0
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        twin(work, outputs[entry], initial, expected, after, kind)
        twins += 1
        seed = (initial.decode() if isinstance(initial, bytes) else '@set' if isinstance(initial, set)
                else '@list' if isinstance(initial, list) else '@missing')
        rows = []
        (work / 'HashProjectionsCases.tet').write_text(source(i))
        code = support.checker.check(work, 'HashProjectionsCases.tet',
            command=[str(ROOT / '_build/default/dev/store_run.exe'), 'HashProjectionsCases.tet',
                     f'case{i}' if isinstance(initial, dict) else entry, KEY, seed, '1000000'], receive=rows.append)
        encoded = (arrays.wire(expected, kind) if kind == 'array' else b'null' if kind == 'null'
                   else kind.encode() + b':' + expected.hex().encode())
        require(code == 0 and rows == [b'REPLY ' + encoded + b'\n'], f'HASH-PROJECTIONS store reply {i}: {rows!r}')
        stores += 1
    print(f'PASS HASH-PROJECTIONS-ORACLES store={stores} luajit={twins}', flush=True)


def refusals(work):
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = []
    for kind in KINDS:
        invalid.append((command(kind).replace(TAG, '(tag b"elsewhere")'), 'Hash', mismatch + b'(In SMu Tag [] (ACtor tag)'))
        invalid += [(command(kind), schema, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode())
                    for schema, ctor in [('(Str Binary)', 'Str'), ('Set', 'Set'), ('List', 'List'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]]
    for i, (cmd, schema, diagnostic) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{i}'
        path.write_text(f'module Refused\nschema jobs : String -> Key {schema} tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ r <- {cmd}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'HASH-PROJECTIONS refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'HASH-PROJECTIONS refusal published output {i}')
    print(f'PASS HASH-PROJECTIONS-REFUSALS cases={len(invalid)} atomic_output={len(invalid)}', flush=True)


def live(work, outputs):
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        hosts = readonly = rejected = errors = 0
        live_cases = cases() + [(cmd, kind, WRONG, kind, 'status') for cmd in KINDS for kind in ('zset', 'stream')]
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
                require(run(args, env=env, code=code) == wanted, f'HASH-PROJECTIONS {host} {entry} reply')
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                if after == initial:
                    require(run(redis + ['DUMP', KEY]) == before, 'HASH-PROJECTIONS preserved complete value')
                else:
                    require(isinstance(after, dict) and run(redis + ['TYPE', KEY]) == b'hash\n', 'HASH-PROJECTIONS updated type')
                    require(run(redis + ['HLEN', KEY]) == str(len(after)).encode() + b'\n', 'HASH-PROJECTIONS updated count')
                    for field, value in after.items():
                        require(run(redis + ['HGET', KEY, field]) == value + b'\n', 'HASH-PROJECTIONS updated field')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'HASH-PROJECTIONS unrelated key')
                hosts, readonly, rejected = hosts + 1, readonly + int(ro), rejected + int(code != 0)
        for cmd in KINDS:
            run(redis + ['FLUSHDB'])
            run(redis + ['SET', KEY, 'wrong'])
            run(redis + ['ACL', 'SETUSER', 'default', '-eval', '-evalsha'])
            output = outputs[cmd + 'Raw']
            for args in (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)], ['/bin/bash', str(output / 'prog.sh')]):
                require(run(args, env=env, code=4) == b'', 'HASH-PROJECTIONS error stops host')
                require(run(redis + ['GET', KEY]) == b'wrong\n', 'HASH-PROJECTIONS error preserves key')
                hosts, readonly, errors = hosts + 1, readonly + 1, errors + 1
        require((hosts, readonly, rejected, errors) == (88, 76, 6, 4), 'HASH-PROJECTIONS host inventory')
        print(f'PASS HASH-PROJECTIONS-E2E cases={len(live_cases)} hosts={hosts} readonly={readonly} '
              f'utf8_refusals={rejected} errors={errors}', flush=True)
    count = 0
    for entry, expected in EXAMPLES.items():
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/HashCatalog.tet', '--entry', entry, '--host', host]) == expected,
                    f'HASH-PROJECTIONS example {entry} {host}')
            count += 1
    print(f'PASS HASH-PROJECTIONS-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline'], ['--artifacts']),
            'Usage: hash-projections-tests.py [--static|--offline|--artifacts|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-hash-projections-') as temporary:
        work = Path(temporary)
        path = work / 'HashProjectionsCases.tet'
        path.write_text(source())
        if probe:
            entry = sys.argv[2]
            require(entry in ENTRIES, 'HASH-PROJECTIONS unknown probe')
            rows = [row for row in cases() if row[0] == entry]
            require(bool(rows), f'HASH-PROJECTIONS entry {entry} has no LuaJIT cases')
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                twin(work, output, initial, expected, after, kind)
            print(f'PASS HASH-PROJECTIONS-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, path, entry) for entry in ENTRIES}
        print(f'PASS HASH-PROJECTIONS-ARTIFACTS pairs={len(outputs)}', flush=True)
        if '--artifacts' not in sys.argv:
            refusals(work)
            for entry, expected in EXAMPLES.items():
                require(run(['./tether', 'run', 'examples/HashCatalog.tet', '--entry', entry]) == expected, 'HASH-PROJECTIONS interpreter example')
            if '--static' not in sys.argv:
                offline(work, outputs)
            if not sys.argv[1:]:
                live(work, outputs)
    mode = f" mode={sys.argv[1].lstrip('-')}" if sys.argv[1:] else ''
    print(f'PASS HASH-PROJECTIONS-TESTS{mode}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL HASH-PROJECTIONS-TESTS {error}', file=sys.stderr)
        sys.exit(1)
