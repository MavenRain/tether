#!/usr/bin/env python3
"""Set commands checked against explicit replies, complete member sets and independent engines."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TAG = '(tag b"team")'
KEY = '{team}:members:red'
BINARY = b'\x00\xff"\n$(touch forbidden)\\member\n'
WRONG = b'WRONGTYPE Operation against a key holding the wrong kind of value'
HASHED = {b'f': b'v'}
READONLY = {'present', 'count', 'presentBinary', 'presentEmpty'}
EXAMPLES = [('main', b'2\n'), ('duplicate', b'0\n'), ('present', b'1\n'), ('deleted', b'0\n')]
EXAMPLE_EXECS = [('main', 'node', b'2\n'), ('main', 'bash', b'2\n'), ('main', 'luajit', b'2\n'),
                 ('duplicate', 'node', b'0\n'), ('present', 'bash', b'1\n'), ('deleted', 'node', b'0\n')]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


support = module('sets_support', 'dev/strings-tests.py')
run, literal, checker, local = support.run, support.literal, support.checker, support.local


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def tet(value):
    return 'b"' + ''.join(f'\\x{byte:02x}' for byte in value) + '"'


def commands():
    base = f'Reply {TAG} (members b"red")'
    return {
        'add': f'sadd {base} b"m"',
        'remove': f'srem {base} b"m"',
        'present': f'sismember {base} b"m"',
        'count': f'scard {base}',
        'addBinary': f'sadd {base} {tet(BINARY)}',
        'removeBinary': f'srem {base} {tet(BINARY)}',
        'presentBinary': f'sismember {base} {tet(BINARY)}',
        'addEmpty': f'sadd {base} b""',
        'removeEmpty': f'srem {base} b""',
        'presentEmpty': f'sismember {base} b""',
    }


def cases():
    rows = [
        ('add', None, b'1', {b'm'}),
        ('add', {b'm'}, b'0', {b'm'}),
        ('add', {b'z'}, b'1', {b'm', b'z'}),
        ('remove', None, b'0', None),
        ('remove', {b'm'}, b'1', None),
        ('remove', {b'm', b'z'}, b'1', {b'z'}),
        ('remove', {b'z'}, b'0', {b'z'}),
        ('present', None, b'0', None),
        ('present', {b'm'}, b'1', {b'm'}),
        ('present', {b'z'}, b'0', {b'z'}),
        ('count', None, b'0', None),
        ('count', {b'm', b'z'}, b'2', {b'm', b'z'}),
        ('count', {b'1', b'01', b'0', b'-0'}, b'4', {b'1', b'01', b'0', b'-0'}),
        ('addBinary', None, b'1', {BINARY}),
        ('addBinary', {BINARY}, b'0', {BINARY}),
        ('removeBinary', {BINARY}, b'1', None),
        ('removeBinary', {BINARY, b'z'}, b'1', {b'z'}),
        ('presentBinary', {BINARY}, b'1', {BINARY}),
        ('presentBinary', {b'z'}, b'0', {b'z'}),
        ('addEmpty', None, b'1', {b''}),
        ('addEmpty', {b''}, b'0', {b''}),
        ('removeEmpty', {b''}, b'1', None),
        ('presentEmpty', {b''}, b'1', {b''}),
        ('presentEmpty', None, b'0', None),
        ('earlier', None, b'1', None),
        ('branch', None, b'0', None),
    ]
    rows.extend((entry, b'wrong', WRONG, b'wrong') for entry in ('add', 'remove', 'present', 'count'))
    rows.extend((entry, HASHED, WRONG, HASHED) for entry in ('add', 'remove', 'present', 'count'))
    return rows


def source():
    declarations = ['module SetCases',
        'schema members : String -> Key Set tag b"team"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs']
    for name, command in commands().items():
        declarations.append(f'def {name}Script : Script Reply {TAG} := do {{ '
            f'r <- {command}; pure Reply {TAG} (expose r) }}')
        declarations.append(f'def {name} : Client Reply := do {{ '
            f'r <- inv Reply {TAG} {name}Script; done Reply r }}')
    declarations.append(f'def earlier : Client Reply := do {{ '
        f'first <- inv Reply {TAG} addScript; _ <- inv Reply {TAG} removeScript; done Reply first }}')
    declarations += [
        f'def choose : Reply -> Script Reply {TAG} := fun (r : Reply) =>',
        f'case r as x in Reply return Script Reply {TAG} with',
        f'| nil => do {{ r <- {commands()["add"]}; pure Reply {TAG} r }}',
        f'| int n => pure Reply {TAG} (int n) | bulk b => pure Reply {TAG} (bulk b)',
        f'| status b => pure Reply {TAG} (status b) | err b => pure Reply {TAG} (err b)',
        f'| array rs => pure Reply {TAG} (array rs)',
        f'def branchScript : Script Reply {TAG} := do {{ r <- {commands()["present"]}; choose r }}',
        f'def branch : Client Reply := do {{ r <- inv Reply {TAG} branchScript; done Reply r }}']
    for index, (entry, initial, _expected, _after) in enumerate(cases()):
        if isinstance(initial, set):
            seeds = ' '.join(f'_ <- sadd Reply {TAG} (members b"red") {tet(member)};'
                             for member in sorted(initial))
            declarations.append(f'def seed{index} : Script Reply {TAG} := do {{ '
                f'{seeds} pure Reply {TAG} nil }}')
            declarations.append(f'def case{index} : Client Reply := do {{ '
                f'_ <- inv Reply {TAG} seed{index}; r <- inv Reply {TAG} {entry}Script; done Reply r }}')
    return '\n'.join(declarations) + '\n'


def lua_members(value):
    return '{' + ','.join('[' + literal(m) + ']=true' for m in sorted(value)) + '}'


def lua_fields(value):
    return '{' + ','.join('[' + literal(f) + ']=' + literal(v) for f, v in sorted(value.items())) + '}'


def seed_argument(initial):
    if isinstance(initial, bytes):
        return initial.decode()
    return '@hash' if isinstance(initial, dict) else '@missing'


def lua(work, output, initial, expected, after):
    scripts = {s['entry']: s for s in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = ['{path=' + literal(output / (scripts[name]['stem'] + '.lua')) + ',keys={' +
             ','.join(literal(k) for k in scripts[name]['keys']) + '}}' for name in plan['invokes']]
    value = (lua_fields(initial) if isinstance(initial, dict)
             else literal(initial) if isinstance(initial, bytes) else 'nil')
    sets = '{[' + literal(KEY) + ']=' + lua_members(initial) + '}' if isinstance(initial, set) else '{}'
    check = ('kind="set",members=' + lua_members(after) if isinstance(after, set)
             else 'kind="hash",fields=' + lua_fields(after) if isinstance(after, dict)
             else 'value=' + ('false' if after is None else literal(after)))
    config = work / 'sets-config.lua'
    kind = '"status"' if expected == WRONG else '"string"'
    config.write_text('return {values={[' + literal(KEY) + ']=' + value + '},sets=' + sets + ',invokes={' +
        ','.join(calls) + '},answer=' + str(plan['answer']) + ',kind=' + kind +
        ',checks={{key=' + literal(KEY) + ',' + check + '}}}\n')
    require(run(['luajit', '-joff', 'dev/lua-store.lua', str(config)]) == expected + b'\n', 'SETS LuaJIT reply')


def offline(work, outputs):
    stores = twins = 0
    for index, (entry, initial, expected, after) in enumerate(cases()):
        lua(work, outputs[entry], initial, expected, after)
        twins += 1
        rows = []
        code = checker.check(work, 'SetCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
            'SetCases.tet', f'case{index}' if isinstance(initial, set) else entry, KEY,
            seed_argument(initial), '1000000'], receive=rows.append)
        kind = 'status' if expected == WRONG else 'int'
        require(code == 0 and rows == [f'REPLY {kind}:{expected.hex()}\n'.encode()],
                f'SETS store reply {index}: {rows!r}')
        stores += 1
    print(f'PASS SETS-ORACLES store={stores} luajit={twins}', flush=True)


def refusals(work):
    prefix = 'module Refused\nschema members : String -> Key SCHEMA tag b"team"\n'
    typed = ('add', 'remove', 'present', 'count')
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = [(commands()[name].replace(TAG, '(tag b"elsewhere")'), 'Set',
                mismatch + b'(In SMu Tag [] (ACtor tag)') for name in typed]
    for schema, constructor in [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('List', 'List')]:
        diagnostic = mismatch + f'(In SMu RedisType [] (ACtor {constructor})'.encode()
        invalid += [(commands()[name], schema, diagnostic) for name in typed]
    unbound = b'CHECK unbound: signed64Bytes is not a constructor of Bytes'
    invalid += [(f'{name} Reply {TAG} (members b"red") (int64 b"1")', 'Set', unbound)
                for name in ('sadd', 'srem', 'sismember')]
    atomic = 0
    for index, (command, schema, diagnostic) in enumerate(invalid):
        path = work / 'Refused.tet'
        path.write_text(prefix.replace('SCHEMA', schema) +
            f'def s : Script Reply {TAG} := do {{ r <- {command}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        output = work / f'refused-{index}'
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT,
                                capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr,
                f'SETS refusal {index}: {result.returncode} {result.stderr!r}')
        atomic += int(not output.exists())
    require(atomic == len(invalid), 'SETS refusal published output')
    print(f'PASS SETS-REFUSALS cases={len(invalid)} atomic_output={atomic}', flush=True)


def live(work, outputs):
    with local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        hosts = readonly = 0
        for entry, initial, expected, after in cases():
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                if isinstance(initial, set):
                    for member in sorted(initial):
                        seed = "return redis.call('SADD',KEYS[1]," + literal(member) + ')'
                        require(run(redis + ['EVAL', seed, '1', KEY]) == b'1\n', 'SETS seed')
                elif isinstance(initial, dict):
                    for field, value in sorted(initial.items()):
                        require(run(redis + ['HSET', KEY, field, value]) == b'1\n', 'SETS hash seed')
                elif initial is not None:
                    require(run(redis + ['-x', 'SET', KEY], data=initial) == b'OK\n', 'SETS wrong-type seed')
                ro = entry in READONLY
                run(redis + ['ACL', 'SETUSER', 'default', '-eval' if ro else '+eval', '-evalsha' if ro else '+evalsha'])
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                require(run(args, env=env) == expected + b'\n', f'SETS {host} {entry} reply')
                readonly += int(ro)
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                kind = (b'none' if after is None else b'set' if isinstance(after, set)
                        else b'hash' if isinstance(after, dict) else b'string')
                require(run(redis + ['TYPE', KEY]) == kind + b'\n', f'SETS {host} key type')
                if isinstance(after, set):
                    require(run(redis + ['SCARD', KEY]) == str(len(after)).encode() + b'\n', 'SETS stored cardinality')
                    for member in sorted(after):
                        read = "return redis.call('SISMEMBER',KEYS[1]," + literal(member) + ')'
                        require(run(redis + ['EVAL', read, '1', KEY]) == b'1\n', 'SETS stored member')
                elif isinstance(after, dict):
                    for field, value in sorted(after.items()):
                        require(run(redis + ['HGET', KEY, field]) == value + b'\n', 'SETS preserved hash')
                elif after is not None:
                    require(run(redis + ['GET', KEY]) == after + b'\n', 'SETS preserved wrong type')
                hosts += 1
        print(f'PASS SETS-E2E cases={len(cases())} hosts={hosts} readonly={readonly}', flush=True)
    execs = 0
    for entry, host, expected in EXAMPLE_EXECS:
        args = ['./tether', 'exec', 'examples/Sets.tet']
        args += [] if entry == 'main' else ['--entry', entry]
        require(run(args + ['--host', host]) == expected, f'SETS example exec {entry} {host}')
        execs += 1
    print(f'PASS SETS-EXAMPLE exec={execs}', flush=True)


def main():
    require(sys.argv[1:] in ([], ['--static'], ['--offline']), 'Usage: sets-tests.py [--static|--offline]')
    with tempfile.TemporaryDirectory(prefix='tether-sets-') as temporary:
        work = Path(temporary)
        path = work / 'SetCases.tet'
        path.write_text(source())
        outputs = {}
        for entry in (*commands(), 'earlier', 'branch'):
            output = work / entry
            run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
            require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'SETS canonical bodies')
            for script in json.loads((output / 'scripts.json').read_text()):
                ro = script['entry'] in {name + 'Script' for name in READONLY}
                body = (output / (script['stem'] + '.lua')).read_bytes()
                require(body.startswith(b'#!lua flags=no-writes\n') == ro, 'SETS write classification')
            outputs[entry] = output
        print(f'PASS SETS-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES:
            require(run(['./tether', 'run', 'examples/Sets.tet', '--entry', entry]) == expected, 'SETS example')
        if '--static' not in sys.argv:
            offline(work, outputs)
        if not sys.argv[1:]:
            live(work, outputs)
    print('PASS SETS-TESTS', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL SETS-TESTS {error}', file=sys.stderr)
        sys.exit(1)
