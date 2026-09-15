#!/usr/bin/env python3
"""Set destinations, aliasing, atomic errors and parity with local Redis."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('set_store_algebra', ROOT / 'dev/set-algebra-tests.py')
algebra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(algebra)
arrays, support = algebra.arrays, algebra.support
run, require, literal = support.run, support.require, support.literal
TAG = '(tag b"store")'
KEYS = tuple('{store}:teams:' + key for key in ('destination', 'left', 'right'))
KINDS = ('union', 'inter', 'diff')
SUFFIXES = ('', 'Left', 'Right', 'Same', 'AllSame', 'Reverse', 'Within', 'Earlier', 'Typed', 'Snapshot', 'Raw')
ENTRIES = tuple(kind + suffix for kind in KINDS for suffix in SUFFIXES)
EXAMPLES = {'main': b'["alice","bob","carol"]\n', 'retained': b'1\n', 'exclusive': b'["alice"]\n'}
INITIAL = ({b'old'}, {b'a', b'c'}, {b'b', b'c'})


def operands(suffix):
    destination = 1 if suffix in ('Left', 'AllSame') else 2 if suffix == 'Right' else 0
    left, right = (2, 1) if suffix == 'Reverse' else (1, 1) if suffix in ('Same', 'AllSame') else (1, 2)
    return destination, left, right


def case(kind, suffix, before):
    destination, left, right = operands(suffix)
    if any(value is not None and not isinstance(value, set) for value in (before[left], before[right])):
        return kind + suffix, before, support.WRONG, before, 'status', False
    members = algebra.operation(kind, before[left], before[right])
    after = list(before)
    after[destination] = set(members) if members else None
    reply, reply_kind = str(len(members)).encode(), 'bulk'
    if suffix in ('Within', 'Earlier'):
        after[destination] = None
    elif suffix == 'Typed':
        reply, reply_kind = b'integer', 'status'
    elif suffix == 'Snapshot':
        reply, reply_kind = members, 'array'
    return kind + suffix, before, reply, tuple(after), reply_kind, True


def cases():
    inputs = [(None, None), ({b'a', b'b'}, None), (None, {b'a', b'b'}), INITIAL[1:],
              ({b'a'}, {b'b'}), ({b'a\0', b'a', b''}, {b'aa', b'a', b'\0'}),
              ({b'10', b'2'}, {b'01', b'2'}), ({support.TEXT, b''}, {'café'.encode(), b''}),
              ({bytes([i]) for i in range(256)}, {b'', b'\xff'}),
              ({f'm{i:03}'.encode() for i in range(129)}, {f'm{i:03}'.encode() for i in range(65)})]
    rows = []
    for kind in KINDS:
        rows += [case(kind, '', ({b'f': b'v'}, *pair)) for pair in inputs]
        rows += [case(kind, '', (old, *INITIAL[1:])) for old in (None, {b'old'}, b'old', [b'old'])]
        rows += [case(kind, suffix, (INITIAL[0], *pair)) for suffix in ('Left', 'Right') for pair in inputs[:5]]
        for bad in (b'wrong', {b'f': b'v'}, [b'm']):
            for good in (None, {b'a'}):
                for pair in ((bad, good), (good, bad)):
                    rows += [case(kind, suffix, (INITIAL[0], *pair)) for suffix in ('', 'Left', 'Right')]
        rows += [case(kind, suffix, INITIAL) for suffix in ('Same', 'AllSame', 'Reverse', 'Within', 'Earlier', 'Typed', 'Snapshot')]
    require(len(rows) == 201, 'SET-STORE case inventory')
    return rows


def source(entry):
    kind = next(k for k in KINDS if entry.startswith(k))
    suffix = entry[len(kind):]
    destination, left, right = operands(suffix)
    keys = tuple(f'(teams b"{key}")' for key in ('destination', 'left', 'right'))
    command = f's{kind}store Reply {TAG} {keys[destination]} {keys[left]} {keys[right]}'
    declarations = ['module SetStoreCases', 'schema teams : String -> Key Set tag b"store"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        'def typed : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| int n => status b"integer" | nil => nil | bulk b => status b"wrong"',
        '| status b => status b"wrong" | err b => status b | array rs => status b"wrong"',
        f'def removeScript : Script Reply {TAG} := do {{ _ <- del Reply Set {TAG} {keys[destination]}; pure Reply {TAG} nil }}']
    tail = f'_ <- del Reply Set {TAG} {keys[destination]}; ' if suffix == 'Within' else ''
    if suffix == 'Snapshot':
        tail += f'members <- smembers Reply {TAG} {keys[destination]}; '
    answer = 'r' if suffix in ('Raw', 'Within') else 'typed r' if suffix == 'Typed' else 'members' if suffix == 'Snapshot' else 'expose r'
    declarations += [f'def {entry}Script : Script Reply {TAG} := do {{ r <- {command}; {tail}pure Reply {TAG} ({answer}) }}']
    later = f'_ <- inv Reply {TAG} removeScript; ' if suffix in ('Earlier', 'Raw') else ''
    declarations += [f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; {later}done Reply r }}']
    return '\n'.join(declarations) + '\n'


def emit(work, entry):
    path, output = work / 'SetStoreCases.tet', work / entry
    path.write_text(source(entry))
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'SET-STORE canonical bodies')
    suffix = entry[len(next(k for k in KINDS if entry.startswith(k))):]
    destination, left, right = operands(suffix)
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(body.startswith(b'#!lua\n'), 'SET-STORE write classification')
        indices = (destination,) if script['entry'] == 'removeScript' else (destination, left, right)
        require(script['keys'] == sorted({KEYS[i] for i in indices}), 'SET-STORE declared keys')
    return output


def twin(work, output, row):
    _entry, before, expected, after, kind, _success = row
    algebra.twin(work, output, before, expected, after, kind, keys=KEYS, reason='SET-STORE LuaJIT reply')


def refusals(work):
    invalid = []
    mismatch = b'CHECK mismatch: the constructor keyBytes of Key gives the index '
    for kind in KINDS:
        for side in range(3):
            for schema, ctor in [('(Str Binary)', 'Str'), ('Hash', 'Hash'), ('List', 'List'), ('ZSet', 'ZSet'), ('Stream', 'Stream')]:
                types, tags = ['Set'] * 3, ['store'] * 3
                types[side] = schema
                invalid.append((kind, types, tags, mismatch + f'(In SMu RedisType [] (ACtor {ctor})'.encode()))
            tags = ['store'] * 3
            tags[side] = 'elsewhere'
            invalid.append((kind, ['Set'] * 3, tags, mismatch + b'(In SMu Tag [] (ACtor tag)'))
    for index, (kind, types, tags, diagnostic) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{index}'
        path.write_text('module Refused\n' + '\n'.join(
            f'schema {name} : String -> Key {schema} tag b"{tag}"' for name, schema, tag in zip(('destination', 'left', 'right'), types, tags)) +
            f'\ndef s : Script Reply {TAG} := do {{ r <- s{kind}store Reply {TAG} (destination b"x") (left b"x") (right b"x"); pure Reply {TAG} r }}\n'
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and diagnostic in result.stderr, f'SET-STORE refusal {index}: {result.stderr!r}')
        require(not output.exists(), f'SET-STORE refusal published output {index}')
    require(len(invalid) == 54, 'SET-STORE refusal inventory')
    print(f'PASS SET-STORE-REFUSALS cases={len(invalid)} atomic_output={len(invalid)}', flush=True)


def live(work, outputs):
    extra = []
    for kind in KINDS:
        for bad in ('zset', 'stream'):
            extra.append(case(kind, '', (bad, *INITIAL[1:])))
            for good in (None, {b'a'}):
                for pair in ((bad, good), (good, bad)):
                    extra += [case(kind, suffix, (INITIAL[0], *pair)) for suffix in ('', 'Left', 'Right')]
    members_hex = "local o={}; for _,v in ipairs(redis.call('SMEMBERS',KEYS[1])) do o[#o+1]=(v:gsub('.',function(c) return string.format('%02x',string.byte(c)) end)) end; table.sort(o); return table.concat(o,',')"
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        run(redis + ['ACL', 'SETUSER', 'default', '-eval_ro', '-evalsha_ro'])
        hosts = errors = 0
        for row in cases() + extra:
            entry, initial, expected, after, reply_kind, success = row
            suffix = entry[len(next(k for k in KINDS if entry.startswith(k))):]
            destination, _left, _right = operands(suffix)
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', 'other', 'kept'])
                for key, value in zip(KEYS, initial):
                    algebra.seed(redis, key, value)
                    run(redis + ['EXPIRE', key, '600'])
                snapshots = [run(redis + ['DUMP', key]) for key in KEYS]
                output = outputs[entry]
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                require(run(args, env=env) == arrays.stdout(expected, reply_kind), f'SET-STORE {host} {entry} reply')
                for index, (key, previous, final, snapshot) in enumerate(zip(KEYS, initial, after, snapshots)):
                    if not success or index != destination:
                        require(run(redis + ['DUMP', key]) == snapshot, 'SET-STORE preserved complete value')
                        expiry = run(redis + ['TTL', key])
                        require(int(expiry) > 0 if previous is not None else expiry == b'-2\n',
                                'SET-STORE preserved expiry')
                    elif final is None:
                        require(run(redis + ['EXISTS', key]) == b'0\n', 'SET-STORE empty result deletes destination')
                    else:
                        require(run(redis + ['TYPE', key]) == b'set\n', 'SET-STORE destination type')
                        require(run(redis + ['SCARD', key]) == str(len(final)).encode() + b'\n', 'SET-STORE destination cardinality')
                        require(run(redis + ['EVAL', members_hex, '1', key]) == b','.join(sorted(v.hex().encode() for v in final)) + b'\n',
                                'SET-STORE destination members')
                        require(run(redis + ['TTL', key]) == b'-1\n', 'SET-STORE replacement clears expiry')
                require(run(redis + ['GET', 'other']) == b'kept\n', 'SET-STORE unrelated key')
                hosts += 1
        for kind in KINDS:
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                run(redis + ['SET', KEYS[0], 'kept'])
                run(redis + ['SET', KEYS[2], 'wrong'])
                output = outputs[kind + 'Raw']
                args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                        if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                require(run(args, env=env, code=4) == b'', 'SET-STORE error stops host')
                require(run(redis + ['GET', KEYS[0]]) == b'kept\n', 'SET-STORE error stops later invocation')
                require(run(redis + ['GET', KEYS[2]]) == b'wrong\n', 'SET-STORE error preserves source')
                hosts, errors = hosts + 1, errors + 1
        require((len(extra), hosts, errors) == (78, 564, 6), 'SET-STORE host inventory')
        print(f'PASS SET-STORE-E2E cases=279 hosts={hosts} errors={errors}', flush=True)
    count = 0
    for entry, expected in EXAMPLES.items():
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/TeamCache.tet', '--entry', entry, '--host', host]) == expected,
                    f'SET-STORE example {entry} {host}')
            count += 1
    print(f'PASS SET-STORE-EXAMPLE exec={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--static'], ['--offline']),
            'Usage: set-store-tests.py [--static|--offline|--probe ENTRY]')
    with tempfile.TemporaryDirectory(prefix='tether-set-store-') as temporary:
        work = Path(temporary)
        if probe:
            entry = sys.argv[2]
            rows = [row for row in cases() if row[0] == entry]
            require(bool(rows), 'SET-STORE probe has no cases')
            output = emit(work, entry)
            for row in rows:
                twin(work, output, row)
            print(f'PASS SET-STORE-PROBE entry={entry} cases={len(rows)}', flush=True)
            return
        outputs = {entry: emit(work, entry) for entry in ENTRIES}
        print(f'PASS SET-STORE-ARTIFACTS pairs={len(outputs)}', flush=True)
        refusals(work)
        for entry, expected in EXAMPLES.items():
            require(run(['./tether', 'run', 'examples/TeamCache.tet', '--entry', entry]) == expected, 'SET-STORE interpreter example')
        print(f'PASS SET-STORE-STORE-EXAMPLE cases={len(EXAMPLES)}', flush=True)
        if '--static' not in sys.argv:
            for row in cases():
                twin(work, outputs[row[0]], row)
            print(f'PASS SET-STORE-ORACLES luajit={len(cases())}', flush=True)
        if not sys.argv[1:]:
            live(work, outputs)
    mode = f" mode={sys.argv[1].lstrip('-')}" if sys.argv[1:] else ''
    print(f'PASS SET-STORE-TESTS{mode}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL SET-STORE-TESTS {error}', file=sys.stderr)
        sys.exit(1)
