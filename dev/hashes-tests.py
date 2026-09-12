#!/usr/bin/env python3
"""Hash commands compared with explicit replies, stored fields and independent engines."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TAG = '(tag b"account")'
KEY = '{account}:profiles:alice'
FIELD = b'\x00\xff"\n$(touch forbidden)\\field'
BINARY = b'\xff\x00"\n$(touch forbidden)\\value'
TEXT = b'\x00\xef\xbb\xbf"\n$(touch forbidden)\\value\n'
WRONG = b'WRONGTYPE Operation against a key holding the wrong kind of value'
INVALID = b'ERR hash value is not an integer'
OVERFLOW = b'ERR increment or decrement would overflow'
READONLY = {'read', 'present', 'length', 'readBinary'}
EXAMPLES = [('main', b'9007199254740993\n'), ('name', b'Alice\n'), ('deleted', b'0\n')]
EXAMPLE_EXECS = [('main', 'node', b'9007199254740993\n'), ('main', 'bash', b'9007199254740993\n'),
                 ('main', 'luajit', b'9007199254740993\n'), ('name', 'node', b'Alice\n'),
                 ('deleted', 'bash', b'0\n')]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


support = module('hashes_support', 'dev/strings-tests.py')
run, literal, checker, local = support.run, support.literal, support.checker, support.local


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def tet(value):
    return 'b"' + ''.join(f'\\x{byte:02x}' for byte in value) + '"'


def commands():
    key = '(profiles b"alice")'
    base = f'Reply {TAG} {key}'
    return {
        'write': f'hset {base} b"f" {tet(BINARY)}',
        'read': f'hget {base} b"f"',
        'erase': f'hdel {base} b"f"',
        'present': f'hexists {base} b"f"',
        'length': f'hlen {base}',
        'add': f'hincrby {base} b"f" (int64 b"1")',
        'subtract': f'hincrby {base} b"f" (int64 b"-2")',
        'minimum': f'hincrby {base} b"f" (int64 b"-9223372036854775808")',
        'writeBinary': f'hset {base} {tet(FIELD)} {tet(BINARY)}',
        'readBinary': f'hget {base} {tet(FIELD)}',
        'empty': f'hset {base} b"" b""',
    }


def cases():
    rows = [
        ('write', None, b'1', {b'f': BINARY}, 'int'),
        ('write', {b'f': b'old', b'other': b'kept'}, b'0', {b'f': BINARY, b'other': b'kept'}, 'int'),
        ('read', None, b'', None, 'null'),
        ('read', {b'other': b'kept'}, b'', {b'other': b'kept'}, 'null'),
        ('read', {b'f': b''}, b'', {b'f': b''}, 'bulk'),
        ('read', {b'f': BINARY}, BINARY, {b'f': BINARY}, 'bulk'),
        ('read', {b'f': TEXT}, TEXT, {b'f': TEXT}, 'bulk'),
        ('erase', None, b'0', None, 'int'),
        ('erase', {b'f': b'old'}, b'1', None, 'int'),
        ('erase', {b'f': b'old', b'other': b'kept'}, b'1', {b'other': b'kept'}, 'int'),
        ('erase', {b'other': b'kept'}, b'0', {b'other': b'kept'}, 'int'),
        ('present', None, b'0', None, 'int'),
        ('present', {b'f': b''}, b'1', {b'f': b''}, 'int'),
        ('present', {b'other': b'kept'}, b'0', {b'other': b'kept'}, 'int'),
        ('length', None, b'0', None, 'int'),
        ('length', {b'f': b'one', b'other': b'two'}, b'2', {b'f': b'one', b'other': b'two'}, 'int'),
        ('add', None, b'1', {b'f': b'1'}, 'int'),
        ('add', {b'other': b'kept'}, b'1', {b'f': b'1', b'other': b'kept'}, 'int'),
        ('add', {b'f': b'9007199254740992'}, b'9007199254740993', {b'f': b'9007199254740993'}, 'int'),
        ('add', {b'f': b'9223372036854775807'}, OVERFLOW, {b'f': b'9223372036854775807'}, 'bulk'),
        ('subtract', {b'f': b'1'}, b'-1', {b'f': b'-1'}, 'int'),
        ('subtract', {b'f': b'-9223372036854775808'}, OVERFLOW, {b'f': b'-9223372036854775808'}, 'bulk'),
        ('minimum', None, b'-9223372036854775808', {b'f': b'-9223372036854775808'}, 'int'),
        ('minimum', {b'f': b'9223372036854775807'}, b'-1', {b'f': b'-1'}, 'int'),
        ('minimum', {b'f': b'-1'}, OVERFLOW, {b'f': b'-1'}, 'bulk'),
        ('writeBinary', None, b'1', {FIELD: BINARY}, 'int'),
        ('readBinary', {FIELD: BINARY}, BINARY, {FIELD: BINARY}, 'bulk'),
        ('readBinary', {FIELD: TEXT}, TEXT, {FIELD: TEXT}, 'bulk'),
        ('empty', None, b'1', {b'': b''}, 'int'),
        ('earlier', None, b'1', None, 'int'),
    ]
    rows.extend(('add', {b'f': v}, INVALID, {b'f': v}, 'bulk')
                for v in (b'', b'01', b'+1', b'-0', b'0x10', b'9223372036854775808'))
    rows.extend((entry, b'wrong', WRONG, b'wrong', 'bulk')
                for entry in ('write', 'read', 'erase', 'present', 'length', 'add'))
    return rows


def source():
    declarations = ['module HashCases',
        'schema profiles : String -> Key Hash tag b"account"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => bulk b | array rs => array rs']
    for name, command in commands().items():
        declarations.append(f'def {name}Script : Script Reply {TAG} := do {{ '
            f'r <- {command}; pure Reply {TAG} (expose r) }}')
        declarations.append(f'def {name} : Client Reply := do {{ '
            f'r <- inv Reply {TAG} {name}Script; done Reply r }}')
    declarations.append(f'def earlier : Client Reply := do {{ '
        f'first <- inv Reply {TAG} writeScript; _ <- inv Reply {TAG} eraseScript; done Reply first }}')
    for index, (entry, initial, _expected, _after, _kind) in enumerate(cases()):
        if isinstance(initial, dict):
            seeds = ' '.join(f'_ <- hset Reply {TAG} (profiles b"alice") {tet(f)} {tet(v)};'
                             for f, v in initial.items())
            declarations.append(f'def seed{index} : Script Reply {TAG} := do {{ '
                f'{seeds} pure Reply {TAG} nil }}')
            declarations.append(f'def case{index} : Client Reply := do {{ '
                f'_ <- inv Reply {TAG} seed{index}; r <- inv Reply {TAG} {entry}Script; done Reply r }}')
    return '\n'.join(declarations) + '\n'


def lua_value(value):
    if isinstance(value, dict):
        return '{' + ','.join('[' + literal(k) + ']=' + literal(v) for k, v in value.items()) + '}'
    return 'nil' if value is None else literal(value)


def lua(work, output, initial, expected, after):
    scripts = {s['entry']: s for s in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = ['{path=' + literal(output / (scripts[name]['stem'] + '.lua')) + ',keys={' +
             ','.join(literal(k) for k in scripts[name]['keys']) + '}}' for name in plan['invokes']]
    check = ('kind="hash",fields=' + lua_value(after) if isinstance(after, dict)
             else 'value=' + ('false' if after is None else literal(after)))
    config = work / 'hashes-config.lua'
    config.write_text('return {values={[' + literal(KEY) + ']=' + lua_value(initial) + '},invokes={' +
        ','.join(calls) + '},answer=' + str(plan['answer']) + ',checks={{key=' + literal(KEY) + ',' + check + '}}}\n')
    require(run(['luajit', '-joff', 'dev/lua-store.lua', str(config)]) == expected + b'\n', 'HASHES LuaJIT reply')


def offline(work, outputs):
    stores = twins = 0
    for index, (entry, initial, expected, after, kind) in enumerate(cases()):
        lua(work, outputs[entry], initial, expected, after)
        twins += 1
        rows = []
        code = checker.check(work, 'HashCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
            'HashCases.tet', f'case{index}' if isinstance(initial, dict) else entry, KEY,
            initial.decode() if isinstance(initial, bytes) else '@missing', '1000000'], receive=rows.append)
        want = b'REPLY null\n' if kind == 'null' else f'REPLY {kind}:{expected.hex()}\n'.encode()
        require(code == 0 and rows == [want], f'HASHES store reply {index}: {rows!r}')
        stores += 1
    print(f'PASS HASHES-ORACLES store={stores} luajit={twins}', flush=True)


def refusals(work):
    key = '(profiles b"alice")'
    prefix = 'module Refused\nschema profiles : String -> Key SCHEMA tag b"account"\n'
    # Every row carries its own schema and its own full diagnostic, so no row
    # can silently take the schema or the expectation of another row.
    typed = ('write', 'read', 'erase', 'present', 'length', 'add')
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    wrong_tag = mismatch + b'(In SMu Tag [] (ACtor tag)'
    wrong_key = (mismatch + b'(In SMu RedisType [] (ACtor Str) [(In SMu Encoding [] (ACtor Binary) [])])'
                 b' and the type asks for (In SMu RedisType [] (ACtor Hash) [])')
    invalid = [(command.replace(TAG, '(tag b"elsewhere")'), 'Hash', wrong_tag)
               for name, command in commands().items() if name in typed]
    invalid += [(f'hincrby Reply {TAG} {key} b"f" b"1"', 'Hash', b'CHECK unbound'),
                (f'hincrby Reply {TAG} {key} b"f" (int64 b"9223372036854775808")', 'Hash', b'INT64'),
                (f'hset Reply {TAG} {key} b"f" (int64 b"1")', 'Hash', b'CHECK'),
                (f'get Reply Binary {TAG} {key}', 'Hash', b'WRONGTYPE GET requires a Str key')]
    # Refuse every hash command on a String key, even when the tag agrees.
    invalid += [(command, '(Str Binary)', wrong_key) for name, command in commands().items()
                if name in typed]
    atomic = 0
    for index, (command, schema, diagnostic) in enumerate(invalid):
        header = prefix.replace('SCHEMA', schema)
        path = work / 'Refused.tet'
        path.write_text(header + f'def s : Script Reply {TAG} := do {{ r <- {command}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        output = work / f'refused-{index}'
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT,
                                capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr,
                f'HASHES refusal {index}: {result.returncode} {result.stderr!r}')
        atomic += int(not output.exists())
    require(atomic == len(invalid), 'HASHES refusal published output')
    print(f'PASS HASHES-REFUSALS cases={len(invalid)} atomic_output={atomic}', flush=True)


def live(work, outputs):
    with local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        hosts = readonly = rejected = 0
        for entry, initial, expected, after, _kind in cases():
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                if isinstance(initial, dict):
                    for field, value in initial.items():
                        seed = "return redis.call('HSET',KEYS[1]," + literal(field) + ',' + literal(value) + ')'
                        require(run(redis + ['EVAL', seed, '1', KEY]) == b'1\n', 'HASHES seed')
                elif initial is not None:
                    require(run(redis + ['-x', 'SET', KEY], data=initial) == b'OK\n', 'HASHES wrong-type seed')
                ro = entry in READONLY
                run(redis + ['ACL', 'SETUSER', 'default', '-eval' if ro else '+eval', '-evalsha' if ro else '+evalsha'])
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                # The existing Node and REST text hosts reject invalid UTF-8 replies.
                try:
                    expected.decode('utf-8')
                    code, stdout = 0, expected + b'\n'
                except UnicodeDecodeError:
                    code, stdout = 4, b''
                require(run(args, env=env, code=code) == stdout, f'HASHES {host} {entry} reply')
                rejected += int(code != 0)
                readonly += int(ro)
                run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                kind = b'none' if after is None else b'hash' if isinstance(after, dict) else b'string'
                require(run(redis + ['TYPE', KEY]) == kind + b'\n', f'HASHES {host} key type')
                if isinstance(after, dict):
                    require(run(redis + ['HLEN', KEY]) == str(len(after)).encode() + b'\n', 'HASHES stored field count')
                    for field, value in after.items():
                        read = "return redis.call('HGET',KEYS[1]," + literal(field) + ')'
                        require(run(redis + ['EVAL', read, '1', KEY]) == value + b'\n', 'HASHES stored field')
                elif after is not None:
                    require(run(redis + ['GET', KEY]) == after + b'\n', 'HASHES preserved wrong type')
                hosts += 1
        print(f'PASS HASHES-E2E cases={len(cases())} hosts={hosts} readonly={readonly} utf8_refusals={rejected}', flush=True)
    # The documented exec forms of the example, each with its own local store.
    execs = 0
    for entry, host, expected in EXAMPLE_EXECS:
        args = ['./tether', 'exec', 'examples/Hashes.tet']
        args += [] if entry == 'main' else ['--entry', entry]
        require(run(args + ['--host', host]) == expected, f'HASHES example exec {entry} {host}')
        execs += 1
    print(f'PASS HASHES-EXAMPLE exec={execs}', flush=True)


def main():
    require(sys.argv[1:] in ([], ['--static'], ['--offline']), 'Usage: hashes-tests.py [--static|--offline]')
    with tempfile.TemporaryDirectory(prefix='tether-hashes-') as temporary:
        work = Path(temporary)
        path = work / 'HashCases.tet'
        path.write_text(source())
        outputs = {}
        for entry in (*commands(), 'earlier'):
            output = work / entry
            run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
            require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'HASHES canonical bodies')
            for script in json.loads((output / 'scripts.json').read_text()):
                ro = script['entry'] in {name + 'Script' for name in READONLY}
                body = (output / (script['stem'] + '.lua')).read_bytes()
                require(body.startswith(b'#!lua flags=no-writes\n') == ro, 'HASHES write classification')
            outputs[entry] = output
        print(f'PASS HASHES-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES:
            require(run(['./tether', 'run', 'examples/Hashes.tet', '--entry', entry]) == expected, 'HASHES example')
        if '--static' not in sys.argv:
            offline(work, outputs)
        if not sys.argv[1:]:
            live(work, outputs)
    print('PASS HASHES-TESTS', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL HASHES-TESTS {error}', file=sys.stderr)
        sys.exit(1)
