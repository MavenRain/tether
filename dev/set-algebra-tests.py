#!/usr/bin/env python3
"""Two-key Set algebra, byte ordering, retained replies and host parity."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('set_algebra_arrays', ROOT / 'dev/list-range-tests.py')
arrays = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arrays)
support = arrays.support
run, require, tet, literal = support.run, support.require, support.tet, support.literal
TAG = '(tag b"algebra")'
KEYS = ('{algebra}:teams:left', '{algebra}:teams:right')
KINDS = ('union', 'inter', 'diff')
SUFFIXES = ('', 'Same', 'Reverse', 'Head', 'Earlier', 'Within', 'Branch', 'Raw')
ENTRIES = tuple(kind + suffix for kind in KINDS for suffix in SUFFIXES)
EXAMPLES = {'main': b'["alice","bob","carol"]\n', 'common': b'["bob"]\n',
            'exclusive': b'["alice"]\n', 'retained': b'["bob"]\n'}


def operation(kind, left, right):
    a, b = left or set(), right or set()
    return sorted(a | b if kind == 'union' else a & b if kind == 'inter' else a - b)


def cases():
    rows = []
    initial = ({b'a', b'c'}, {b'b', b'c'})
    for kind in KINDS:
        for left, right in [(None, None), ({b'b', b'a'}, None), (None, {b'b', b'a'}), initial,
                ({b'b'}, {b'a'}), ({b'a\0', b'a', b''}, {b'aa', b'a', b'\0'}),
                ({b'10', b'2'}, {b'01', b'2'}), ({support.TEXT, b''}, {'café'.encode(), b''}),
                ({bytes([i]) for i in range(256)}, {b'', b'\xff'}),
                ({f'm{i:03}'.encode() for i in range(129)}, {f'm{i:03}'.encode() for i in range(65)})]:
            rows.append((kind, (left, right), operation(kind, left, right), (left, right), 'array'))
        for bad in (b'wrong', {b'f': b'v'}, [b'm']):
            for opposite in (None, {b'a'}):
                for before in ((bad, opposite), (opposite, bad)):
                    rows.append((kind, before, support.WRONG, before, 'status'))
        rows += [(kind + 'Same', initial, [] if kind == 'diff' else sorted(initial[0]), initial, 'array'),
                 (kind + 'Reverse', initial, operation(kind, *reversed(initial)), initial, 'array'),
                 (kind + 'Head', initial, operation(kind, *initial)[0], initial, 'bulk'),
                 (kind + 'Head', ({b''}, {b''} if kind != 'diff' else None), b'',
                  ({b''}, {b''} if kind != 'diff' else None), 'bulk'),
                 (kind + 'Head', (None, None), None, (None, None), 'null')]
        for suffix in ('Earlier', 'Within', 'Branch'):
            after = initial if suffix == 'Branch' else (None, None)
            rows.append((kind + suffix, initial, operation(kind, *initial), after, 'array'))
    require(len(rows) == 90, 'SET-ALGEBRA case inventory')
    return rows


def source(entry):
    kind = next(k for k in KINDS if entry.startswith(k))
    suffix = entry[len(kind):]
    left, right = '(teams b"left")', '(teams b"right")'
    if suffix == 'Same':
        right = left
    if suffix == 'Reverse':
        left, right = right, left
    command = f's{kind} Reply {TAG} {left} {right}'
    declarations = ['module SetAlgebraCases', 'schema teams : String -> Key Set tag b"algebra"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        'def first : Replies -> Reply := fun (rs : Replies) => case rs as x in Replies return Reply with',
        '| repliesNil => nil | repliesCons r rest => r',
        'def headReply : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => first rs',
        f'def removeScript : Script Reply {TAG} := do {{ '
        f'_ <- del Reply Set {TAG} (teams b"left"); _ <- del Reply Set {TAG} (teams b"right"); pure Reply {TAG} nil }}',
        f'def choose : Reply -> Script Reply {TAG} := fun (r : Reply) =>',
        f'case r as x in Reply return Script Reply {TAG} with',
        f'| nil => pure Reply {TAG} nil | int n => removeScript',
        f'| bulk b => pure Reply {TAG} (bulk b) | status b => pure Reply {TAG} (status b)',
        f'| err b => pure Reply {TAG} (err b) | array rs => pure Reply {TAG} (array rs)']
    result = 'r' if suffix in ('Raw', 'Within') else 'headReply r' if suffix == 'Head' else 'expose r'
    tail = (f'_ <- del Reply Set {TAG} (teams b"left"); _ <- del Reply Set {TAG} (teams b"right"); '
            if suffix == 'Within' else '')
    finish = 'choose r' if suffix == 'Branch' else f'pure Reply {TAG} ({result})'
    declarations += [f'def {entry}Script : Script Reply {TAG} := do {{ r <- {command}; {tail}{finish} }}']
    later = f'_ <- inv Reply {TAG} removeScript; ' if suffix == 'Earlier' else ''
    declarations += [f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; {later}done Reply r }}']
    return '\n'.join(declarations) + '\n'


def emit(work, entry):
    path, output = work / 'SetAlgebraCases.tet', work / entry
    path.write_text(source(entry))
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'SET-ALGEBRA canonical bodies')
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        readonly = script['entry'] != 'removeScript' and not script['entry'].endswith(('WithinScript', 'BranchScript'))
        require(body.startswith(b'#!lua flags=no-writes\n') == readonly, 'SET-ALGEBRA write classification')
        keys = [KEYS[0]] if entry.endswith('Same') else list(KEYS)
        require(script['keys'] == keys, f'SET-ALGEBRA declared keys {script["keys"]!r}')
    return output


def twin(work, output, before, expected, after, kind):
    scripts = {s['entry']: s for s in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = ['{path=' + literal(output / (scripts[name]['stem'] + '.lua')) + ',keys={' +
             ','.join(literal(k) for k in scripts[name]['keys']) + '}}' for name in plan['invokes']]
    values, sets, lists, checks = ['other="kept"'], [], [], ['{key="other",value="kept"}']
    for key, initial, final in zip(KEYS, before, after):
        binding = '[' + literal(key) + ']='
        if isinstance(initial, set):
            sets.append(binding + support.lua_members(initial))
        elif isinstance(initial, list):
            lists.append(binding + support.lua_items(initial))
        elif isinstance(initial, dict):
            values.append(binding + support.lua_fields(initial))
        elif initial is not None:
            values.append(binding + literal(initial))
        check = ('kind="set",members=' + support.lua_members(final) if isinstance(final, set)
                 else 'kind="list",items=' + support.lua_items(final) if isinstance(final, list)
                 else 'kind="hash",fields=' + support.lua_fields(final) if isinstance(final, dict)
                 else 'value=' + ('false' if final is None else literal(final)))
        checks.append('{key=' + literal(key) + ',' + check + '}')
    reply_kind = 'nil' if kind == 'null' else 'string' if kind == 'bulk' else kind
    config = work / 'algebra-config.lua'
    config.write_text('return {values={' + ','.join(values) + '},sets={' + ','.join(sets) +
        '},lists={' + ','.join(lists) + '},invokes={' + ','.join(calls) + '},answer=' + str(plan['answer']) +
        ',kind="' + reply_kind + '",reply=true,checks={' + ','.join(checks) + '}}\n')
    encoded = (arrays.wire(expected, kind) if kind == 'array' else b'null' if kind == 'null'
               else kind.encode() + b':' + expected.hex().encode())
    require(run(['luajit', '-joff', 'dev/lua-store.lua', str(config)]) == encoded + b'\n', 'SET-ALGEBRA LuaJIT reply')


def refusals(work):
    invalid = []
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    for kind in KINDS:
        for side in (0, 1):
            for schema, ctor in [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('List', 'List'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]:
                types, tags = ['Set', 'Set'], ['algebra', 'algebra']
                types[side] = schema
                invalid.append((kind, types, tags, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode()))
            tags = ['algebra', 'algebra']
            tags[side] = 'elsewhere'
            invalid.append((kind, ['Set', 'Set'], tags, mismatch + b'(In SMu Tag [] (ACtor tag)'))
    for i, (kind, types, tags, diagnostic) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{i}'
        path.write_text('module Refused\n' + '\n'.join(
            f'schema {name} : String -> Key {schema} tag b"{tag}"' for name, schema, tag in zip(('left', 'right'), types, tags)) +
            f'\ndef s : Script Reply {TAG} := do {{ r <- s{kind} Reply {TAG} (left b"x") (right b"x"); pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'SET-ALGEBRA refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'SET-ALGEBRA refusal published output {i}')
    require(len(invalid) == 36, 'SET-ALGEBRA refusal inventory')
    print(f'PASS SET-ALGEBRA-REFUSALS cases={len(invalid)} atomic_output={len(invalid)}', flush=True)


def seed(redis, key, value):
    if value is None:
        return
    if isinstance(value, set):
        for member in sorted(value, reverse=True):
            run(redis + ['EVAL', "return redis.call('SADD',KEYS[1]," + literal(member) + ')', '1', key])
    elif isinstance(value, bytes):
        run(redis + ['-x', 'SET', key], data=value)
    elif isinstance(value, dict):
        for field, member in value.items():
            run(redis + ['HSET', key, field, member])
    elif isinstance(value, list):
        run(redis + ['RPUSH', key, *value])
    elif value == 'zset':
        run(redis + ['ZADD', key, '1', 'm'])
    elif value == 'stream':
        run(redis + ['XADD', key, '*', 'f', 'v'])
    else:
        raise AssertionError('SET-ALGEBRA unknown seed')


def live(work, outputs):
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        hosts = readonly = rejected = errors = 0
        extra = [(kind, before, support.WRONG, before, 'status') for kind in KINDS
                 for bad in ('zset', 'stream') for good in (None, {b'a'}) for before in ((bad, good), (good, bad))]
        for entry, initial, expected, after, kind in cases() + extra:
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                for key, value in zip(KEYS, initial):
                    seed(redis, key, value)
                before = [run(redis + ['DUMP', key]) for key in KEYS]
                ro = not entry.endswith(('Earlier', 'Within', 'Branch'))
                run(redis + ['ACL', 'SETUSER', 'default', '-eval' if ro else '+eval', '-evalsha' if ro else '+evalsha'])
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                try:
                    wanted, code = arrays.stdout(expected, kind), 0
                except UnicodeDecodeError:
                    wanted, code = b'', 4
                require(run(args, env=env, code=code) == wanted, f'SET-ALGEBRA {host} {entry} reply')
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                for key, previous, final, snapshot in zip(KEYS, initial, after, before):
                    if final == previous:
                        require(run(redis + ['DUMP', key]) == snapshot, 'SET-ALGEBRA preserved complete value')
                    else:
                        require(final is None and run(redis + ['EXISTS', key]) == b'0\n', 'SET-ALGEBRA deleted key')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'SET-ALGEBRA unrelated key')
                hosts, readonly, rejected = hosts + 1, readonly + int(ro), rejected + int(code != 0)
        for kind in KINDS:
            run(redis + ['FLUSHDB'])
            run(redis + ['SET', KEYS[1], 'wrong'])
            run(redis + ['ACL', 'SETUSER', 'default', '-eval', '-evalsha'])
            output = outputs[kind + 'Raw']
            for args in (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)], ['/bin/bash', str(output / 'prog.sh')]):
                require(run(args, env=env, code=4) == b'', 'SET-ALGEBRA error stops host')
                require(run(redis + ['GET', KEYS[1]]) == b'wrong\n', 'SET-ALGEBRA error preserves key')
                hosts, readonly, errors = hosts + 1, readonly + 1, errors + 1
            run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
        require((hosts, readonly, rejected, errors) == (234, 216, 6, 6), 'SET-ALGEBRA host inventory')
        print(f'PASS SET-ALGEBRA-E2E cases=114 hosts={hosts} readonly={readonly} utf8_refusals={rejected} errors={errors}', flush=True)
    count = 0
    for entry, expected in EXAMPLES.items():
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/TeamAccess.tet', '--entry', entry, '--host', host]) == expected,
                    f'SET-ALGEBRA example {entry} {host}')
            count += 1
    print(f'PASS SET-ALGEBRA-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline']),
            'Usage: set-algebra-tests.py [--static|--offline|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-set-algebra-') as temporary:
        work = Path(temporary)
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(bool(rows), 'SET-ALGEBRA probe has no cases')
            output = emit(work, entry)
            for _entry, before, expected, after, kind in rows:
                twin(work, output, before, expected, after, kind)
            print(f'PASS SET-ALGEBRA-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, entry) for entry in ENTRIES}
        print(f'PASS SET-ALGEBRA-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES.items():
            require(run(['./tether', 'run', 'examples/TeamAccess.tet', '--entry', entry]) == expected, 'SET-ALGEBRA interpreter example')
        print(f'PASS SET-ALGEBRA-STORE-EXAMPLE cases={len(EXAMPLES)}', flush=True)
        if '--static' not in sys.argv:
            for entry, before, expected, after, kind in cases():
                twin(work, outputs[entry], before, expected, after, kind)
            print(f'PASS SET-ALGEBRA-ORACLES luajit={len(cases())}', flush=True)
        if not sys.argv[1:]:
            live(work, outputs)
    mode = f" mode={sys.argv[1].lstrip('-')}" if sys.argv[1:] else ''
    print(f'PASS SET-ALGEBRA-TESTS{mode}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL SET-ALGEBRA-TESTS {error}', file=sys.stderr)
        sys.exit(1)
