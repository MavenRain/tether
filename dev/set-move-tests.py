#!/usr/bin/env python3
"""Set transfers, no-op ordering, atomic errors and Redis host parity."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('set_move_algebra', ROOT / 'dev/set-algebra-tests.py')
algebra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(algebra)
arrays, support = algebra.arrays, algebra.support
run, require, tet = support.run, support.require, support.tet
TAG = '(tag b"move")'
KEYS = ('{move}:teams:source', '{move}:teams:destination')
MEMBERS = {'empty': b'', 'binary': b'\0\xff\n', 'unicode': 'café'.encode(),
           'quoted': b'"\'\\\n$()`'}
ENTRIES = ('move', 'same', 'reverse', *MEMBERS, 'within', 'earlier', 'typed', 'snapshot', 'raw')
EXAMPLES = {'main': b'["alice","carol"]\n', 'retained': b'1\n', 'unchanged': b'1\n'}


def operands(entry):
    return (0, 0) if entry == 'same' else (1, 0) if entry == 'reverse' else (0, 1)


def case(entry, before):
    source, destination = operands(entry)
    member = MEMBERS.get(entry, b'm')
    left, right = before[source], before[destination]
    if left is not None and (not isinstance(left, set) or (right is not None and not isinstance(right, set))):
        return entry, before, support.WRONG, before, 'status'
    moved = left is not None and member in left
    after = list(before)
    if moved and source != destination:
        after[source] = left - {member} or None
        after[destination] = (right or set()) | {member}
    reply, kind = b'1' if moved else b'0', 'bulk'
    if entry == 'typed':
        reply, kind = b'integer', 'status'
    if entry == 'snapshot':
        reply, kind = sorted(after[destination] or set()), 'array'
    if entry in ('within', 'earlier', 'snapshot'):
        after[destination] = None
    return entry, before, reply, tuple(after), kind


def cases(live=False):
    values = [None, {b'm'}, {b'n'}, {b'm', b'n'}, b'wrong', {b'f': b'v'}, [b'm']]
    if live:
        values += ['zset', 'stream']
    rows = [case(entry, (left, right)) for entry in ('move', 'reverse') for left in values for right in values]
    rows += [case('same', (value, {b'kept'})) for value in values]
    rows += [case(entry, ({member, b'kept'}, None)) for entry, member in MEMBERS.items()]
    rows += [case(entry, ({b'm', b'n'}, {b'm', b'x'})) for entry in ('within', 'earlier', 'typed', 'snapshot')]
    require(len(rows) == (179 if live else 113), 'SET-MOVE case inventory')
    return rows


def source(entry):
    left, right = operands(entry)
    keys = ('(teams b"source")', '(teams b"destination")')
    command = f'smove Reply {TAG} {keys[left]} {keys[right]} {tet(MEMBERS.get(entry, b"m"))}'
    declarations = ['module SetMoveCases', 'schema teams : String -> Key Set tag b"move"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        'def classify : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| int n => status b"integer" | nil => nil | bulk b => status b"wrong"',
        '| status b => status b"wrong" | err b => status b | array rs => status b"wrong"',
        f'def removeScript : Script Reply {TAG} := do {{ _ <- del Reply Set {TAG} {keys[right]}; pure Reply {TAG} nil }}']
    tail = f'values <- smembers Reply {TAG} {keys[right]}; ' if entry == 'snapshot' else ''
    if entry in ('within', 'snapshot'):
        tail += f'_ <- del Reply Set {TAG} {keys[right]}; '
    answer = 'r' if entry == 'raw' else 'classify r' if entry == 'typed' else 'values' if entry == 'snapshot' else 'expose r'
    declarations += [f'def {entry}Script : Script Reply {TAG} := do {{ r <- {command}; {tail}pure Reply {TAG} ({answer}) }}']
    later = f'_ <- inv Reply {TAG} removeScript; ' if entry in ('earlier', 'raw') else ''
    declarations += [f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; {later}done Reply r }}']
    return '\n'.join(declarations) + '\n'


def emit(work, entry):
    path, output = work / 'SetMoveCases.tet', work / entry
    path.write_text(source(entry))
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'SET-MOVE canonical bodies')
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(body.startswith(b'#!lua\n'), 'SET-MOVE write classification')
        indices = (operands(entry)[1],) if script['entry'] == 'removeScript' else operands(entry)
        require(script['keys'] == sorted({KEYS[i] for i in indices}), 'SET-MOVE declared keys')
    return output


def twin(work, output, row):
    _entry, before, expected, after, kind = row
    algebra.twin(work, output, before, expected, after, kind, keys=KEYS, reason='SET-MOVE LuaJIT reply')


def refusals(work):
    invalid = []
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    for side in (0, 1):
        for schema, ctor in [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('List', 'List'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]:
            types = ['Set', 'Set']
            types[side] = schema
            invalid.append((types, ['move', 'move'], 'b"m"', mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode()))
        tags = ['move', 'move']
        tags[side] = 'elsewhere'
        invalid.append((['Set', 'Set'], tags, 'b"m"', mismatch + b'(In SMu Tag [] (ACtor tag)'))
    invalid += [(['Set', 'Set'], ['move', 'move'], member, diagnostic) for member, diagnostic in (
        ('(int64 b"1")', b'CHECK unbound: signed64Bytes is not a constructor of Bytes'),
        ('(destination b"x")', b'CHECK unbound: keyBytes is not a constructor of Bytes'))]
    for index, (types, tags, member, diagnostic) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{index}'
        path.write_text('module Refused\n' + '\n'.join(
            f'schema {name} : String -> Key {schema} tag b"{tag}"' for name, schema, tag in zip(('source', 'destination'), types, tags)) +
            f'\ndef s : Script Reply {TAG} := do {{ r <- smove Reply {TAG} (source b"x") (destination b"x") {member}; pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'SET-MOVE refusal {index}: {result.stderr!r}')
        require(not output.exists(), f'SET-MOVE refusal published output {index}')
    require(len(invalid) == 14, 'SET-MOVE refusal inventory')
    print(f'PASS SET-MOVE-REFUSALS cases={len(invalid)} atomic_output={len(invalid)}', flush=True)


def live(work, outputs):
    members_hex = "local o={}; for _,v in ipairs(redis.call('SMEMBERS',KEYS[1])) do o[#o+1]=(v:gsub('.',function(c) return string.format('%02x',string.byte(c)) end)) end; table.sort(o); return table.concat(o,',')"
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        run(redis + ['ACL', 'SETUSER', 'default', '-eval_ro', '-evalsha_ro'])
        hosts = errors = 0
        for entry, before, expected, after, kind in cases(live=True):
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                for key, value in zip(KEYS, before):
                    algebra.seed(redis, key, value)
                    run(redis + ['EXPIRE', key, '600'])
                snapshots = [run(redis + ['DUMP', key]) for key in KEYS]
                deadlines = [run(redis + ['PEXPIRETIME', key]) for key in KEYS]
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                require(run(args, env=env) == arrays.stdout(expected, kind), f'SET-MOVE {host} {entry} reply before={before!r}')
                for key, old, final, snapshot, deadline in zip(KEYS, before, after, snapshots, deadlines):
                    if final == old:
                        require(run(redis + ['DUMP', key]) == snapshot, 'SET-MOVE unchanged complete value')
                    elif final is None:
                        require(run(redis + ['EXISTS', key]) == b'0\n', 'SET-MOVE last member deletes source')
                    else:
                        require(run(redis + ['TYPE', key]) == b'set\n', 'SET-MOVE destination type')
                        require(run(redis + ['SCARD', key]) == str(len(final)).encode() + b'\n', 'SET-MOVE cardinality')
                        require(run(redis + ['EVAL', members_hex, '1', key]) == b','.join(sorted(v.hex().encode() for v in final)) + b'\n',
                                'SET-MOVE complete members')
                    expiry = b'-2\n' if final is None else b'-1\n' if old is None else deadline
                    require(run(redis + ['PEXPIRETIME', key]) == expiry, 'SET-MOVE exact expiry preservation')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'SET-MOVE unrelated key')
                hosts += 1
        for host in ('node', 'bash'):
            run(redis + ['FLUSHDB'])
            run(redis + ['SET', KEYS[0], 'wrong'])
            run(redis + ['SADD', KEYS[1], 'kept'])
            output = outputs['raw']
            args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                    if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
            require(run(args, env=env, code=4) == b'', 'SET-MOVE error stops host')
            require(run(redis + ['GET', KEYS[0]]) == b'wrong\n', 'SET-MOVE error preserves source')
            require(run(redis + ['SMEMBERS', KEYS[1]]) == b'kept\n', 'SET-MOVE error stops later invocation')
            hosts, errors = hosts + 1, errors + 1
        require((hosts, errors) == (360, 2), 'SET-MOVE host inventory')
        print(f'PASS SET-MOVE-E2E cases=179 hosts={hosts} errors={errors}', flush=True)
    count = 0
    for entry, expected in EXAMPLES.items():
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/TeamTransfer.tet', '--entry', entry, '--host', host]) == expected,
                    f'SET-MOVE example {entry} {host}')
            count += 1
    print(f'PASS SET-MOVE-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline']),
            'Usage: set-move-tests.py [--static|--offline|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-set-move-') as temporary:
        work = Path(temporary)
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(bool(rows), 'SET-MOVE probe has no cases')
            output = emit(work, entry)
            for row in rows:
                twin(work, output, row)
            print(f'PASS SET-MOVE-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, entry) for entry in ENTRIES}
        print(f'PASS SET-MOVE-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES.items():
            require(run(['./tether', 'run', 'examples/TeamTransfer.tet', '--entry', entry]) == expected, 'SET-MOVE interpreter example')
        print(f'PASS SET-MOVE-STORE-EXAMPLE cases={len(EXAMPLES)}', flush=True)
        if '--static' not in sys.argv:
            for row in cases():
                twin(work, outputs[row[0]], row)
            print(f'PASS SET-MOVE-ORACLES luajit={len(cases())}', flush=True)
        if not sys.argv[1:]:
            live(work, outputs)
    mode = f" mode={sys.argv[1].lstrip('-')}" if sys.argv[1:] else ''
    print(f'PASS SET-MOVE-TESTS{mode}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL SET-MOVE-TESTS {error}', file=sys.stderr)
        sys.exit(1)
