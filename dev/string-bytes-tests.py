#!/usr/bin/env python3
"""String byte operations across the store, LuaJIT and actual Redis hosts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('string_bytes_support', ROOT / 'dev/hash-conditional-tests.py')
twins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(twins)
support = twins.support
run, require, tet, literal = support.run, support.require, support.tet, support.literal
TAG, KEY, WRONG = support.TAG, support.KEY, support.WRONG
BASE = f'Reply {TAG} (jobs b"mail")'
LENGTH = f'strlen Reply Binary {TAG} (jobs b"mail")'
BINARY = bytes(range(256))
QUERY = {'extend': f'append {BASE} b"!"', 'empty': f'append {BASE} b""',
         'binary': f'append {BASE} {tet(BINARY)}', 'computed': f'append {BASE} (identity b"!")',
         'length': LENGTH, 'rawLength': LENGTH, 'rawAppend': f'append {BASE} b"!"',
         'within': f'append {BASE} b"!"', 'retained': f'append {BASE} b"!"',
         'lengthWithin': LENGTH, 'lengthRetained': LENGTH}
READONLY = {'lengthScript', 'rawLengthScript', 'lengthRetainedScript'}
EXAMPLES = {'main': b'hello, world\n', 'length': b'12\n', 'retained': b'5\n', 'integerLength': b'16\n'}


def cases():
    rows = []
    for initial in (None, b'', b'hello', 'é🙂'.encode(), b'\x00\xff\x00', b'9007199254740993'):
        for entry, suffix in (('extend', b'!'), ('empty', b''), ('binary', BINARY), ('computed', b'!')):
            after = (initial or b'') + suffix
            rows.append((entry, initial, str(len(after)).encode(), after, 'int'))
        rows.append(('length', initial, str(len(initial or b'')).encode(), initial, 'int'))
    for initial in ({b'f': b'v'}, [b'm'], {b'm'}):
        rows.extend((entry, initial, WRONG, initial, 'status') for entry in ('extend', 'empty', 'length'))
    rows += [(entry, b'abc', b'3' if entry.startswith('length') else b'4', None, 'int')
             for entry in ('within', 'retained', 'lengthWithin', 'lengthRetained')]
    rows += [('rawAppend', b'ab', b'3', b'ab!', 'int'), ('rawLength', b'ab', b'2', b'ab', 'int')]
    require(len(rows) == 45, 'STRING-BYTES inventory')
    return rows


def source(seed=None):
    declarations = ['module StringByteCases', 'schema jobs : String -> Key (Str Binary) tag b"queue"',
        'def identity : Bytes -> Bytes := fun (b : Bytes) => b',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b | status b => status b | err b => status b | array rs => array rs',
        f'def clearScript : Script Reply {TAG} := do {{ r <- del Reply (Str Binary) {TAG} (jobs b"mail"); pure Reply {TAG} r }}']
    for entry, command in QUERY.items():
        clear = f'_ <- del Reply (Str Binary) {TAG} (jobs b"mail"); ' if entry in ('within', 'lengthWithin') else ''
        body = (f'{command} (fun (r : Reply) => pure Reply {TAG} r)' if entry.startswith('raw') else
                f'do {{ r <- {command}; {clear}pure Reply {TAG} (expose r) }}')
        later = f'_ <- inv Reply {TAG} clearScript; ' if entry in ('retained', 'lengthRetained') else ''
        declarations += [f'def {entry}Script : Script Reply {TAG} := {body}',
            f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; {later}done Reply r }}']
    if seed is not None:
        entry, initial = seed
        later = f'_ <- inv Reply {TAG} clearScript; ' if entry in ('retained', 'lengthRetained') else ''
        declarations += [f'def seedScript : Script Reply {TAG} := do {{ r <- set {BASE} {tet(initial)}; pure Reply {TAG} r }}',
            f'def seeded : Client Reply := do {{ _ <- inv Reply {TAG} seedScript; r <- inv Reply {TAG} {entry}Script; {later}done Reply r }}']
    return '\n'.join(declarations) + '\n'


def emit(work, path, entry):
    output = work / ('out-' + entry)
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'STRING-BYTES canonical Lua')
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(body.startswith(b'#!lua flags=no-writes\n') == (script['entry'] in READONLY), 'STRING-BYTES write classification')
    return output


LIMIT = b'ERR string exceeds maximum allowed size (proto-max-bulk-len)'
GUARD = (b'    if #amount > 536870912 or #previous > 536870912 - #amount then\n'
         b"      return {err='" + LIMIT + b"'}\n")


def twin(work, output, initial, expected, after, kind):
    try:
        twins.twin(work, output, initial, expected, after, kind)
    except AssertionError as error:
        raise AssertionError('STRING-BYTES LuaJIT reply' if str(error) == 'HASH-CONDITIONAL LuaJIT reply' else str(error)) from None


def offline(work, outputs):
    require((ROOT / 'store/store.ml').read_bytes().count(LIMIT) == 1
            and (ROOT / 'dev/lua-store.lua').read_bytes().count(GUARD) == 1, 'STRING-BYTES size limit text')
    for i, (entry, initial, expected, after, kind) in enumerate(cases()):
        twin(work, outputs[entry], initial, expected, after, kind)
        seeded = isinstance(initial, bytes)
        (work / 'StringByteCases.tet').write_text(source((entry, initial) if seeded else None))
        seed = '@hash' if isinstance(initial, dict) else '@list' if isinstance(initial, list) else '@set' if isinstance(initial, set) else '@missing'
        rows = []
        code = support.checker.check(work, 'StringByteCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
            'StringByteCases.tet', 'seeded' if seeded else entry, KEY, seed, '1000000'], receive=rows.append)
        require(code == 0 and rows == [b'REPLY ' + kind.encode() + b':' + expected.hex().encode() + b'\n'], f'STRING-BYTES store {i}: {rows!r}')
    print('PASS STRING-BYTES-ORACLES store=45 luajit=45', flush=True)


def refusals(work):
    invalid = []
    for command in (QUERY['extend'], LENGTH):
        invalid += [(command, schema) for schema in ('Hash', 'Set', 'List', 'ZSet', 'Stream')]
        invalid.append((command.replace(TAG, '(tag b"elsewhere")'), '(Str Binary)'))
    invalid += [(QUERY['extend'], '(Str Int64)'), (QUERY['extend'].replace('b"!"', 'nil'), '(Str Binary)'),
                (LENGTH.replace('Binary', 'Int64'), '(Str Binary)')]
    for i, (body, schema) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{i}'
        path.write_text(f'module Refused\nschema jobs : String -> Key {schema} tag b"queue"\n'
            f'def s : Script Reply {TAG} := do {{ r <- {body}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and b'CHECK ' in result.stderr, f'STRING-BYTES refusal {i}: {result.stderr!r}')
        require(not output.exists(), 'STRING-BYTES refusal published output')
    print(f'PASS STRING-BYTES-REFUSALS cases={len(invalid)} atomic_output={len(invalid)}', flush=True)


def live(work, outputs):
    hosts = errors = expired = 0
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        live_cases = cases() + [(entry, kind, WRONG, kind, 'status')
            for entry in ('extend', 'empty', 'length') for kind in ('zset', 'stream')]
        def invoke(output, host, **kw):
            args = ['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)] if host == 'node' else ['/bin/bash', str(output / 'prog.sh')]
            return run(args, env=env, **kw)
        for entry, initial, expected, after, _kind in live_cases:
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                if isinstance(initial, bytes):
                    run(redis + ['-x', 'SET', KEY], data=initial)
                elif isinstance(initial, dict):
                    run(redis + ['HSET', KEY, 'f', 'v'])
                elif isinstance(initial, list):
                    run(redis + ['RPUSH', KEY, 'm'])
                elif isinstance(initial, set):
                    run(redis + ['SADD', KEY, 'm'])
                elif initial == 'zset':
                    run(redis + ['ZADD', KEY, '1', 'm'])
                elif initial == 'stream':
                    run(redis + ['XADD', KEY, '*', 'f', 'v'])
                run(redis + ['PEXPIREAT', KEY, '4102444800000'])
                before, deadline = run(redis + ['DUMP', KEY]), run(redis + ['PEXPIRETIME', KEY])
                readonly = entry + 'Script' in READONLY and entry != 'lengthRetained'
                run(redis + ['ACL', 'SETUSER', 'default', '-eval' if readonly else '+eval', '-evalsha' if readonly else '+evalsha'])
                try:
                    require(invoke(outputs[entry], host) == expected + b'\n', f'STRING-BYTES {host} {entry} reply')
                finally:
                    run(redis + ['ACL', 'SETUSER', 'default', '+eval', '+evalsha'])
                if isinstance(after, bytes):
                    require(run(redis + ['TYPE', KEY]) == b'string\n' and run(redis + ['GET', KEY]) == after + b'\n', 'STRING-BYTES complete bytes')
                    require(run(redis + ['PEXPIRETIME', KEY]) == (b'-1\n' if initial is None else deadline), 'STRING-BYTES retained deadline')
                elif after is None:
                    require(run(redis + ['EXISTS', KEY]) == b'0\n' and run(redis + ['PEXPIRETIME', KEY]) == b'-2\n', 'STRING-BYTES absent key')
                else:
                    require(run(redis + ['DUMP', KEY]) == before and run(redis + ['PEXPIRETIME', KEY]) == deadline, 'STRING-BYTES wrong type unchanged')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'STRING-BYTES unrelated key')
                hosts += 1
        for entry in ('rawAppend', 'rawLength'):
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['HSET', KEY, 'f', 'v'])
                before = run(redis + ['DUMP', KEY])
                require(invoke(outputs[entry], host, code=4) == b'' and run(redis + ['DUMP', KEY]) == before, 'STRING-BYTES unhandled error')
                errors += 1
        for entry, expected in (('extend', b'1\n'), ('length', b'0\n')):
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', KEY, 'old'])
                run(redis + ['PEXPIREAT', KEY, '1'])
                require(invoke(outputs[entry], host) == expected, 'STRING-BYTES expired reply')
                require(run(redis + ['PEXPIRETIME', KEY]) == (b'-1\n' if entry == 'extend' else b'-2\n'), 'STRING-BYTES expired deadline')
                expired += 1
    require((hosts, errors, expired) == (102, 4, 4), 'STRING-BYTES host inventory')
    print(f'PASS STRING-BYTES-E2E cases={len(live_cases)} hosts={hosts} errors={errors} expired={expired}', flush=True)
    for entry, expected in EXAMPLES.items():
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/StringBuffer.tet', '--entry', entry, '--host', host]) == expected, 'STRING-BYTES example')
    print('PASS STRING-BYTES-EXAMPLE exec=12', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline']), 'Usage: string-bytes-tests.py [--static|--offline|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-string-bytes-') as temporary:
        work = Path(temporary)
        path = work / 'StringByteCases.tet'
        path.write_text(source())
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(entry in QUERY and bool(rows), 'STRING-BYTES probe cases')
            output = emit(work, path, entry)
            for _entry, initial, expected, after, kind in rows:
                twin(work, output, initial, expected, after, kind)
            print(f'PASS STRING-BYTES-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, path, entry) for entry in QUERY}
        print(f'PASS STRING-BYTES-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES.items():
            require(run(['./tether', 'run', 'examples/StringBuffer.tet', '--entry', entry]) == expected, 'STRING-BYTES store example')
        if '--static' not in sys.argv:
            offline(work, outputs)
        if not sys.argv[1:]:
            live(work, outputs)
    print('PASS STRING-BYTES-TESTS' + (f' mode={sys.argv[1][2:]}' if sys.argv[1:] else ''), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL STRING-BYTES-TESTS {error}', file=sys.stderr)
        sys.exit(1)
