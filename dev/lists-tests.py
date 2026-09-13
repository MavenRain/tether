#!/usr/bin/env python3
"""List replies and complete ordered state across the store, LuaJIT and live hosts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TAG = '(tag b"queue")'
KEY = '{queue}:jobs:mail'
BINARY = b'\x00\xff"\n$(touch forbidden)\\job\n'
TEXT = b'\xef\xbb\xbfhello\x00\n\n'
WRONG = b'WRONGTYPE Operation against a key holding the wrong kind of value'
READONLY = {'length'}
EXAMPLES = [('main', b'welcome:alice\n'), ('remaining', b'1\n'), ('empty', b'\n')]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


support = module('lists_support', 'dev/strings-tests.py')
run, literal, checker, local = support.run, support.literal, support.checker, support.local


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def tet(value):
    return 'b"' + ''.join(f'\\x{byte:02x}' for byte in value) + '"'


def commands():
    base = f'Reply {TAG} (jobs b"mail")'
    return {'leftPush': f'lpush {base} b"m"', 'rightPush': f'rpush {base} b"m"',
            'leftPop': f'lpop {base}', 'rightPop': f'rpop {base}', 'length': f'llen {base}',
            'leftBinary': f'lpush {base} {tet(BINARY)}', 'rightBinary': f'rpush {base} {tet(BINARY)}'}


def cases():
    rows = [
        ('leftPush', None, b'1', [b'm'], 'int'),
        ('rightPush', None, b'1', [b'm'], 'int'),
        ('leftPush', [b'a', b'z'], b'3', [b'm', b'a', b'z'], 'int'),
        ('rightPush', [b'a', b'z'], b'3', [b'a', b'z', b'm'], 'int'),
        ('leftPush', [b'm'], b'2', [b'm', b'm'], 'int'),
        ('rightPush', [b'm'], b'2', [b'm', b'm'], 'int'),
        ('leftPop', None, b'', None, 'null'),
        ('rightPop', None, b'', None, 'null'),
        ('leftPop', [b'm'], b'm', None, 'bulk'),
        ('rightPop', [b'm'], b'm', None, 'bulk'),
        ('leftPop', [b'a', b'm', b'z'], b'a', [b'm', b'z'], 'bulk'),
        ('rightPop', [b'a', b'm', b'z'], b'z', [b'a', b'm'], 'bulk'),
        ('length', None, b'0', None, 'int'),
        ('length', [b'm', b'm', b'z'], b'3', [b'm', b'm', b'z'], 'int'),
        ('leftBinary', None, b'1', [BINARY], 'int'),
        ('rightBinary', [b'z'], b'2', [b'z', BINARY], 'int'),
        ('leftBinary', [b'z'], b'2', [BINARY, b'z'], 'int'),
        ('earlier', [b'first', b'second'], b'first', None, 'bulk'),
        ('branch', None, b'0', None, 'int'),
    ]
    for entry in ('leftPop', 'rightPop'):
        rows.extend((entry, [value], value, None, 'bulk') for value in (b'', BINARY, TEXT, b'01'))
    for initial in (b'wrong', {b'f': b'v'}, {b'm'}):
        rows.extend((entry, initial, WRONG, initial, 'status')
                    for entry in ('leftPush', 'rightPush', 'leftPop', 'rightPop', 'length'))
    return rows


def source():
    declarations = ['module ListCases', 'schema jobs : String -> Key List tag b"queue"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs']
    for name, command in commands().items():
        declarations.append(f'def {name}Script : Script Reply {TAG} := do {{ '
            f'r <- {command}; pure Reply {TAG} (expose r) }}')
        declarations.append(f'def {name} : Client Reply := do {{ '
            f'r <- inv Reply {TAG} {name}Script; done Reply r }}')
    declarations.append(f'def earlier : Client Reply := do {{ '
        f'first <- inv Reply {TAG} leftPopScript; _ <- inv Reply {TAG} leftPopScript; done Reply first }}')
    declarations += [
        f'def choose : Reply -> Script Reply {TAG} := fun (r : Reply) =>',
        f'case r as x in Reply return Script Reply {TAG} with',
        f'| nil => do {{ r <- {commands()["leftPop"]}; pure Reply {TAG} r }}',
        f'| int n => pure Reply {TAG} (int n) | bulk b => pure Reply {TAG} (bulk b)',
        f'| status b => pure Reply {TAG} (status b) | err b => pure Reply {TAG} (err b)',
        f'| array rs => pure Reply {TAG} (array rs)',
        f'def branchScript : Script Reply {TAG} := do {{ r <- {commands()["length"]}; choose r }}',
        f'def branch : Client Reply := do {{ r <- inv Reply {TAG} branchScript; done Reply r }}']
    for index, (entry, initial, _expected, _after, _kind) in enumerate(cases()):
        if isinstance(initial, list):
            command = f'rpush Reply {TAG} (jobs b"mail")'
            seeds = ' '.join(f'_ <- {command} {tet(value)};' for value in initial)
            declarations.append(f'def seed{index} : Script Reply {TAG} := do {{ '
                f'{seeds} pure Reply {TAG} nil }}')
            declarations.append(f'def case{index} : Client Reply := do {{ '
                f'_ <- inv Reply {TAG} seed{index}; {entry} }}')
    return '\n'.join(declarations) + '\n'


def lua_items(values):
    return '{' + ','.join(literal(value) for value in values) + '}'


def lua_fields(values):
    return '{' + ','.join('[' + literal(k) + ']=' + literal(v) for k, v in sorted(values.items())) + '}'


def lua_members(values):
    return '{' + ','.join('[' + literal(value) + ']=true' for value in sorted(values)) + '}'


def lua(work, output, initial, expected, after, kind):
    scripts = {s['entry']: s for s in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = ['{path=' + literal(output / (scripts[name]['stem'] + '.lua')) + ',keys={' +
             ','.join(literal(k) for k in scripts[name]['keys']) + '}}' for name in plan['invokes']]
    value = (lua_fields(initial) if isinstance(initial, dict)
             else literal(initial) if isinstance(initial, bytes) else 'nil')
    lists = '{[' + literal(KEY) + ']=' + lua_items(initial) + '}' if isinstance(initial, list) else '{}'
    sets = '{[' + literal(KEY) + ']=' + lua_members(initial) + '}' if isinstance(initial, set) else '{}'
    check = ('kind="list",items=' + lua_items(after) if isinstance(after, list)
             else 'kind="hash",fields=' + lua_fields(after) if isinstance(after, dict)
             else 'kind="set",members=' + lua_members(after) if isinstance(after, set)
             else 'value=' + ('false' if after is None else literal(after)))
    config = work / 'lists-config.lua'
    reply_kind = 'nil' if kind == 'null' else 'status' if kind == 'status' else 'string'
    config.write_text('return {values={other="kept",[' + literal(KEY) + ']=' + value + '},lists=' + lists +
        ',sets=' + sets + ',invokes={' + ','.join(calls) + '},answer=' + str(plan['answer']) +
        ',kind="' + reply_kind + '",checks={{key=' + literal(KEY) + ',' + check +
        '},{key="other",value="kept"}}}\n')
    require(run(['luajit', '-joff', 'dev/lua-store.lua', str(config)]) == expected + b'\n', 'LISTS LuaJIT reply')


def offline(work, outputs):
    stores = twins = 0
    for index, (entry, initial, expected, after, kind) in enumerate(cases()):
        lua(work, outputs[entry], initial, expected, after, kind)
        twins += 1
        seed = (initial.decode() if isinstance(initial, bytes) else '@hash' if isinstance(initial, dict)
                else '@set' if isinstance(initial, set) else '@missing')
        rows = []
        code = checker.check(work, 'ListCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
            'ListCases.tet', f'case{index}' if isinstance(initial, list) else entry, KEY,
            seed, '1000000'], receive=rows.append)
        want = 'REPLY null\n' if kind == 'null' else f'REPLY {kind}:{expected.hex()}\n'
        require(code == 0 and rows == [want.encode()], f'LISTS store reply {index}: {rows!r}')
        stores += 1
    require(stores == 42 and twins == 42, f'LISTS oracle count store={stores} luajit={twins}')
    print(f'PASS LISTS-ORACLES store={stores} luajit={twins}', flush=True)


def refusals(work):
    prefix = 'module Refused\nschema jobs : String -> Key SCHEMA tag b"queue"\n'
    typed = ('leftPush', 'rightPush', 'leftPop', 'rightPop', 'length')
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    invalid = [(commands()[name].replace(TAG, '(tag b"elsewhere")'), 'List',
                mismatch + b'(In SMu Tag [] (ACtor tag)') for name in typed]
    for schema, constructor in [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('Set', 'Set'),
                                ('ZSet', 'ZSet'), ('Stream', 'Stream')]:
        diagnostic = mismatch + f'(In SMu RedisType [] (ACtor {constructor})'.encode()
        invalid += [(commands()[name], schema, diagnostic) for name in typed]
    unbound = b'CHECK unbound: signed64Bytes is not a constructor of Bytes'
    invalid += [(f'{name} Reply {TAG} (jobs b"mail") (int64 b"1")', 'List', unbound)
                for name in ('lpush', 'rpush')]
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
                f'LISTS refusal {index}: {result.returncode} {result.stderr!r}')
        atomic += int(not output.exists())
    require(atomic == len(invalid), 'LISTS refusal published output')
    require(len(invalid) == 32 and atomic == 32, f'LISTS refusal count cases={len(invalid)} atomic={atomic}')
    print(f'PASS LISTS-REFUSALS cases={len(invalid)} atomic_output={atomic}', flush=True)


def live(work, outputs):
    with local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        hosts = readonly = rejected = 0
        for entry, initial, expected, after, _kind in cases():
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                if isinstance(initial, (list, set)):
                    command = 'RPUSH' if isinstance(initial, list) else 'SADD'
                    values = initial if isinstance(initial, list) else sorted(initial)
                    for value in values:
                        run(redis + ['EVAL', "return redis.call('" + command + "',KEYS[1]," + literal(value) + ')', '1', KEY])
                elif isinstance(initial, dict):
                    for field, value in sorted(initial.items()):
                        require(run(redis + ['HSET', KEY, field, value]) == b'1\n', 'LISTS hash seed')
                elif initial is not None:
                    require(run(redis + ['-x', 'SET', KEY], data=initial) == b'OK\n', 'LISTS wrong-type seed')
                ro = entry in READONLY
                run(redis + ['ACL', 'SETUSER', 'default', '-eval' if ro else '+eval', '-evalsha' if ro else '+evalsha'])
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                try:
                    expected.decode('utf-8')
                    code, stdout = 0, expected + b'\n'
                except UnicodeDecodeError:
                    code, stdout = 4, b''
                require(run(args, env=env, code=code) == stdout, f'LISTS {host} {entry} reply')
                rejected += int(code != 0)
                readonly += int(ro)
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                kind = (b'none' if after is None else b'list' if isinstance(after, list)
                        else b'hash' if isinstance(after, dict) else b'set' if isinstance(after, set) else b'string')
                require(run(redis + ['TYPE', KEY]) == kind + b'\n', f'LISTS {host} key type')
                if isinstance(after, list):
                    require(run(redis + ['LLEN', KEY]) == str(len(after)).encode() + b'\n', 'LISTS stored length')
                    for index, value in enumerate(after):
                        require(run(redis + ['LINDEX', KEY, str(index)]) == value + b'\n', 'LISTS stored order')
                elif isinstance(after, dict):
                    require(run(redis + ['HLEN', KEY]) == str(len(after)).encode() + b'\n', 'LISTS preserved hash length')
                    for field, value in sorted(after.items()):
                        require(run(redis + ['HGET', KEY, field]) == value + b'\n', 'LISTS preserved hash')
                elif isinstance(after, set):
                    require(run(redis + ['SCARD', KEY]) == str(len(after)).encode() + b'\n', 'LISTS preserved set length')
                    for value in sorted(after):
                        require(run(redis + ['SISMEMBER', KEY, value]) == b'1\n', 'LISTS preserved set')
                elif after is not None:
                    require(run(redis + ['GET', KEY]) == after + b'\n', 'LISTS preserved wrong type')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'LISTS unrelated key')
                hosts += 1
        require(len(cases()) == 42 and hosts == 84 and readonly == 10 and rejected == 4,
                f'LISTS e2e count cases={len(cases())} hosts={hosts} readonly={readonly} utf8_refusals={rejected}')
        print(f'PASS LISTS-E2E cases={len(cases())} hosts={hosts} readonly={readonly} utf8_refusals={rejected}', flush=True)
    execs = 0
    for entry, expected in EXAMPLES:
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/JobQueue.tet', '--entry', entry, '--host', host]) == expected,
                    f'LISTS example exec {entry} {host}')
            execs += 1
    require(execs == 9, f'LISTS example exec count {execs}')
    print(f'PASS LISTS-EXAMPLE exec={execs}', flush=True)


def main():
    require(sys.argv[1:] in ([], ['--static'], ['--offline'], ['--artifacts']),
            'Usage: lists-tests.py [--static|--offline|--artifacts]')
    with tempfile.TemporaryDirectory(prefix='tether-lists-') as temporary:
        work = Path(temporary)
        path = work / 'ListCases.tet'
        path.write_text(source())
        outputs = {}
        for entry in (*commands(), 'earlier', 'branch'):
            output = work / entry
            run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
            require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'LISTS canonical bodies')
            for script in json.loads((output / 'scripts.json').read_text()):
                ro = script['entry'] in {name + 'Script' for name in READONLY}
                body = (output / (script['stem'] + '.lua')).read_bytes()
                require(body.startswith(b'#!lua flags=no-writes\n') == ro, 'LISTS write classification')
            outputs[entry] = output
        require(len(outputs) == 9, f'LISTS artifact pair count {len(outputs)}')
        print(f'PASS LISTS-ARTIFACTS pairs={len(outputs)}', flush=True)
        if '--artifacts' not in sys.argv:
            refusals(work)
            for entry, expected in EXAMPLES:
                require(run(['./tether', 'run', 'examples/JobQueue.tet', '--entry', entry]) == expected, 'LISTS example')
            if '--static' not in sys.argv:
                offline(work, outputs)
            if not sys.argv[1:]:
                live(work, outputs)
    print('PASS LISTS-TESTS', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL LISTS-TESTS {error}', file=sys.stderr)
        sys.exit(1)
