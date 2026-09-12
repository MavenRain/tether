#!/usr/bin/env python3
"""String commands checked against explicit answers and independent engines."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TAG = '(tag b"counter")'
KEY = '{counter}:hits:visits'
BINARY_KEY = '{counter}:payload:message'
WRONG = b'WRONGTYPE Operation against a key holding the wrong kind of value'
OVERFLOW = b'ERR increment or decrement would overflow'
INVALID = b'ERR value is not an integer or out of range'
BINARY = b'\x00\xff"\n$(touch forbidden)\\end'
HASH = 'hash'
INT = b'int'
BULK = b'bulk'
STATUS = b'status'


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


checker = module('strings_checker', 'dev/check.py')
local = module('strings_local', 'bin/local.py')


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def run(args, *, code=0, env=None, data=None):
    result = subprocess.run(args, cwd=ROOT, input=data, env=env, capture_output=True, timeout=120)
    require(result.returncode == code, f'{args}: exit={result.returncode}\n{result.stdout!r}\n{result.stderr!r}')
    return result.stdout


def literal(value):
    data = value if isinstance(value, bytes) else str(value).encode()
    return '"' + ''.join(f'\\{byte:03d}' for byte in data) + '"'


def commands():
    key = '(hits b"visits")'
    return {
        'add': f'incrby Reply {TAG} {key} (int64 b"1")',
        'subtract': f'incrby Reply {TAG} {key} (int64 b"-2")',
        'minimum': f'incrby Reply {TAG} {key} (int64 b"-9223372036854775808")',
        'decrement': f'decr Reply {TAG} {key}',
        'number': f'setInt64 Reply {TAG} {key} (int64 b"9007199254740993")',
        'binary': f'set Reply {TAG} (payload b"message") b"' +
                  ''.join(f'\\x{byte:02x}' for byte in BINARY) + '"',
        'erase': f'del Reply (Str Int64) {TAG} {key}',
        'present': f'exists Reply (Str Int64) {TAG} {key}',
    }


def source():
    declarations = ['module StringCases',
        'schema hits : String -> Key (Str Int64) tag b"counter"',
        'schema payload : String -> Key (Str Binary) tag b"counter"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => bulk b | array rs => array rs']
    for name, command in commands().items():
        declarations.append(f'def {name}Script : Script Reply {TAG} := do {{ '
            f'r <- {command}; pure Reply {TAG} (expose r) }}')
        declarations.append(f'def {name} : Client Reply := do {{ '
            f'r <- inv Reply {TAG} {name}Script; done Reply r }}')
    declarations.append(f'def earlier : Client Reply := do {{ '
        f'first <- inv Reply {TAG} numberScript; _ <- inv Reply {TAG} eraseScript; done Reply first }}')
    return '\n'.join(declarations) + '\n'


def cases():
    return [
        ('add', None, b'1', b'1', INT), ('add', b'-1', b'0', b'0', INT),
        ('add', b'9007199254740992', b'9007199254740993', b'9007199254740993', INT),
        ('add', b'9223372036854775807', OVERFLOW, b'9223372036854775807', BULK),
        ('add', b'01', INVALID, b'01', BULK), ('add', HASH, WRONG, HASH, BULK),
        ('subtract', b'1', b'-1', b'-1', INT), ('subtract', b'-99', b'-101', b'-101', INT),
        ('subtract', b'-9223372036854775808', OVERFLOW, b'-9223372036854775808', BULK),
        ('minimum', None, b'-9223372036854775808', b'-9223372036854775808', INT),
        ('minimum', b'9223372036854775807', b'-1', b'-1', INT),
        ('minimum', b'-1', OVERFLOW, b'-1', BULK),
        ('decrement', None, b'-1', b'-1', INT),
        ('decrement', b'9007199254740994', b'9007199254740993', b'9007199254740993', INT),
        ('decrement', b'-9223372036854775808', OVERFLOW, b'-9223372036854775808', BULK),
        ('decrement', HASH, WRONG, HASH, BULK),
        ('number', None, b'OK', b'9007199254740993', STATUS),
        ('number', HASH, b'OK', b'9007199254740993', STATUS),
        ('binary', None, b'OK', BINARY, STATUS), ('binary', HASH, b'OK', BINARY, STATUS),
        ('erase', None, b'0', None, INT), ('erase', b'old', b'1', None, INT),
        ('erase', HASH, b'1', None, INT),
        ('present', None, b'0', None, INT), ('present', b'old', b'1', b'old', INT),
        ('present', HASH, b'1', HASH, INT), ('earlier', None, b'OK', None, STATUS),
    ]


def lua(work, output, key, initial, expected, after):
    scripts = {s['entry']: s for s in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = []
    for name in plan['invokes']:
        script = scripts[name]
        calls.append('{path=' + literal(output / (script['stem'] + '.lua')) + ',keys={' +
                     ','.join(literal(k) for k in script['keys']) + '}}')
    value = '{}' if initial == HASH else literal(initial) if initial is not None else 'nil'
    check = 'kind="hash"' if after == HASH else 'value=' + (literal(after) if after is not None else 'false')
    config = work / 'strings-config.lua'
    config.write_text('return {values={[' + literal(key) + ']=' + value + '},invokes={' +
                     ','.join(calls) + '},answer=' + str(plan['answer']) +
                     ',checks={{key=' + literal(key) + ',' + check + '}}}\n')
    require(run(['luajit', '-joff', 'dev/lua-store.lua', str(config)]) == expected + b'\n',
            'STRINGS LuaJIT reply')


def store(work, entry, key, initial, expected, constructor):
    rows = []
    code = checker.check(work, 'StringCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
        'StringCases.tet', entry, key, '@missing' if initial is None else initial.decode(), '1000000'],
        receive=rows.append)
    require(code == 0 and len(rows) == 1 and rows[0].startswith(b'REPLY '), 'STRINGS store response')
    kind, sep, payload = rows[0][6:].strip().partition(b':')
    require(sep and kind == constructor and bytes.fromhex(payload.decode()) == expected,
            f'STRINGS store reply {rows!r}')


def refusals(work):
    key = '(hits b"visits")'
    prefix = 'module Refused\nschema hits : String -> Key (Str Int64) tag b"counter"\n'
    invalid = [
        (f'set Reply {TAG} {key} b"bad"', b'CHECK mismatch'),
        (f'setInt64 Reply {TAG} {key} b"1"', b'CHECK unbound: bytesCons is not a constructor of Signed64'),
        (f'incrby Reply {TAG} {key} b"1"', b'CHECK unbound: bytesCons is not a constructor of Signed64'),
        (f'incrby Reply {TAG} {key} (int64 b"9223372036854775808")', b'INT64'),
        (f'setInt64 Reply {TAG} {key} (int64 b"01")', b'INT64'),
        (f'decr Reply (tag b"elsewhere") {key}', b'CHECK mismatch'),
        (f'del Reply Hash {TAG} {key}', b'CHECK mismatch'),
        (f'exists Reply Hash {TAG} {key}', b'CHECK mismatch'),
    ]
    atomic = 0
    for index, (command, diagnostic) in enumerate(invalid):
        path = work / 'Refused.tet'
        path.write_text(prefix + f'def s : Script Reply {TAG} := do {{ r <- {command}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        output = work / f'refused-{index}'
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT,
                                capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr,
                f'STRINGS refusal {index}: {result.returncode} {result.stderr!r}')
        atomic += 0 if output.exists() else 1
    require(atomic == len(invalid), f'STRINGS refusal output published {len(invalid) - atomic}')
    print(f'PASS STRINGS-REFUSALS cases={len(invalid)} atomic_output={atomic}', flush=True)


def offline(work, outputs):
    stores = twins = 0
    for entry, initial, expected, after, constructor in cases():
        key = BINARY_KEY if entry == 'binary' else KEY
        lua(work, outputs[entry], key, initial, expected, after)
        twins += 1
        if initial != HASH:
            store(work, entry, key, initial, expected, constructor)
            stores += 1
    print(f'PASS STRINGS-ORACLES store={stores} luajit={twins}', flush=True)


def live(work, outputs):
    with local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        hosts = 0
        for entry, initial, expected, after, _constructor in cases():
            key = BINARY_KEY if entry == 'binary' else KEY
            output = outputs[entry]
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                if initial == HASH:
                    require(run(redis + ['HSET', key, 'field', 'value']) == b'1\n', 'STRINGS hash seed')
                elif initial is not None:
                    require(run(redis + ['-x', 'SET', key], data=initial) == b'OK\n', 'STRINGS string seed')
                # EXISTS must run under an ACL that forbids ordinary EVALSHA.
                readonly = entry == 'present'
                run(redis + ['ACL', 'SETUSER', 'default', '-eval' if readonly else '+eval',
                             '-evalsha' if readonly else '+evalsha'])
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                require(run(args, env=env) == expected + b'\n', f'STRINGS {host} {entry} reply')
                require(run(redis + ['EXISTS', key]) == (b'0\n' if after is None else b'1\n'), 'STRINGS key presence')
                if after == HASH:
                    require(run(redis + ['HGET', key, 'field']) == b'value\n', 'STRINGS preserved hash')
                elif after is not None:
                    require(run(redis + ['GET', key]) == after + b'\n', f'STRINGS {host} stored effect')
                hosts += 1
        print(f'PASS STRINGS-E2E cases={len(cases())} hosts={hosts}', flush=True)


def main():
    require(sys.argv[1:] in ([], ['--static'], ['--offline']), 'Usage: strings-tests.py [--static|--offline]')
    with tempfile.TemporaryDirectory(prefix='tether-strings-') as temporary:
        work = Path(temporary)
        path = work / 'StringCases.tet'
        path.write_text(source())
        outputs = {}
        for entry in (*commands(), 'earlier'):
            output = work / entry
            run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
            require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'STRINGS canonical bodies')
            for script in json.loads((output / 'scripts.json').read_text()):
                readonly = script['entry'] == 'presentScript'
                body = (output / (script['stem'] + '.lua')).read_bytes()
                require(body.startswith(b'#!lua flags=no-writes\n') == readonly, 'STRINGS write classification')
            outputs[entry] = output
        print(f'PASS STRINGS-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in [('main', b'9007199254740993\n'), ('binary', b'hello\n'), ('deleted', b'0\n')]:
            require(run(['./tether', 'run', 'examples/Strings.tet', '--entry', entry]) == expected, 'STRINGS example')
        if '--static' not in sys.argv:
            offline(work, outputs)
        if not sys.argv[1:]:
            live(work, outputs)
    print('PASS STRINGS-TESTS', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL STRINGS-TESTS {error}', file=sys.stderr)
        sys.exit(1)
