#!/usr/bin/env python3
"""Typed LMOVE artifacts, retained replies, complete state and expiry parity."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('list_move_support', ROOT / 'dev/lists-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, tet, literal = support.run, support.require, support.tet, support.literal
TAG = '(tag b"queue")'
KEYS = ('{queue}:jobs:source', '{queue}:jobs:destination')
ENDS = {'L': 'listLeft', 'R': 'listRight'}
ENTRIES = tuple(prefix + pair for prefix in ('move', 'same') for pair in ('LL', 'LR', 'RL', 'RR')) + (
    'computed', 'within', 'retained', 'raw', 'snapshot', 'nilRetained')
DEADLINES = ('4102444800000', '4102444801000')
EXAMPLES = {'main': b'welcome:alice\n', 'retained': b'welcome:alice\n',
            'rotated': b'["welcome:bob","welcome:alice"]\n'}


def command(entry):
    pair = entry[-2:] if entry.startswith(('move', 'same')) else 'LR'
    target = 'source' if entry.startswith('same') else 'destination'
    sides = [ENDS[side] for side in pair]
    if entry == 'computed':
        sides = [f'(endIdentity {side})' for side in sides]
    return f'lmove Reply {TAG} (jobs b"source") (jobs b"{target}") ' + ' '.join(sides)


def cases():
    rows = []
    for pair, reply, src, dst in [
        ('LL', b'a', [b'b', b'c'], [b'a', b'x', b'y']),
        ('LR', b'a', [b'b', b'c'], [b'x', b'y', b'a']),
        ('RL', b'c', [b'a', b'b'], [b'c', b'x', b'y']),
        ('RR', b'c', [b'a', b'b'], [b'x', b'y', b'c'])]:
        entry = 'move' + pair
        rows.append((entry, [b'a', b'b', b'c'], [b'x', b'y'], reply, src, dst, 'bulk'))
        rows.extend((entry, None, initial, None, None, initial, 'null') for initial in (None, [b'x']))
        rows.append((entry, [b'a', b'b', b'c'], None, reply, src, [reply], 'bulk'))
        rows.append((entry, [b'a'], [b'x'], b'a', None,
                     [b'a', b'x'] if pair[1] == 'L' else [b'x', b'a'], 'bulk'))
    for pair, reply, after in [('LL', b'a', [b'a', b'b', b'c']), ('LR', b'a', [b'b', b'c', b'a']),
                             ('RL', b'c', [b'c', b'a', b'b']), ('RR', b'c', [b'a', b'b', b'c'])]:
        rows += [('same' + pair, [b'a', b'b', b'c'], [b'x'], reply, after, [b'x'], 'bulk'),
                 ('same' + pair, [b'a'], None, b'a', [b'a'], None, 'bulk')]
    rows += [('moveLR', [value], None, value, None, [value], 'bulk') for value in
             (b'', bytes(range(256)), support.TEXT, b'01', b'9007199254740993')]
    for wrong in (b'wrong', {b'f': b'v'}, {b'm'}):
        rows += [('moveLR', wrong, [b'x'], support.WRONG, wrong, [b'x'], 'status'),
                 ('moveLR', [b'a'], wrong, support.WRONG, [b'a'], wrong, 'status'),
                 ('moveLR', None, wrong, None, None, wrong, 'null')]
    rows += [('computed', [b'a', b'b'], [b'x'], b'a', [b'b'], [b'x', b'a'], 'bulk'),
             ('within', [b'a', b'b'], [b'x'], b'a', None, None, 'bulk'),
             ('retained', [b'a', b'b'], [b'x'], b'a', None, None, 'bulk'),
             ('raw', [b'a', b'b'], [b'x'], b'a', [b'b'], [b'x', b'a'], 'bulk'),
             ('snapshot', [b'a', b'b'], [b'x'], [b'x', b'a'], [b'b'], [b'x', b'a'], 'array'),
             ('nilRetained', None, None, None, [b'later'], None, 'null')]
    require(len(rows) == 48, 'LIST-MOVE case inventory')
    return rows


def source(seed=None):
    declarations = ['module ListMoveCases', 'schema jobs : String -> Key List tag b"queue"',
        'def endIdentity : ListEnd -> ListEnd := fun (side : ListEnd) => side',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs']
    clear = f'_ <- del Reply List {TAG} (jobs b"source"); r <- del Reply List {TAG} (jobs b"destination");'
    declarations += [f'def clearScript : Script Reply {TAG} := do {{ {clear} pure Reply {TAG} r }}',
        f'def laterScript : Script Reply {TAG} := do {{ r <- rpush Reply {TAG} (jobs b"source") b"later"; pure Reply {TAG} r }}']
    for entry in ENTRIES:
        next_step = (f'_ <- del Reply List {TAG} (jobs b"source"); _ <- del Reply List {TAG} (jobs b"destination"); ' if entry == 'within' else
                     f'view <- lrange Reply {TAG} (jobs b"destination") (int64 b"0") (int64 b"-1"); ' if entry == 'snapshot' else '')
        result = 'view' if entry == 'snapshot' else 'expose r'
        body = (f'{command(entry)} (fun (r : Reply) => pure Reply {TAG} r)' if entry == 'raw' else
                f'do {{ r <- {command(entry)}; {next_step}pure Reply {TAG} ({result}) }}')
        later = f'_ <- inv Reply {TAG} clearScript; ' if entry == 'retained' else f'_ <- inv Reply {TAG} laterScript; ' if entry == 'nilRetained' else ''
        declarations += [f'def {entry}Script : Script Reply {TAG} := {body}',
            f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; {later}done Reply r }}']
    if seed is not None:
        entry, left, right, *_ = seed
        steps = []
        for name, initial in [('source', left), ('destination', right)]:
            key = f'(jobs b"{name}")'
            if isinstance(initial, list):
                steps.extend(f'_ <- rpush Reply {TAG} {key} {tet(v)};' for v in initial)
        declarations += [f'def seedScript : Script Reply {TAG} := do {{ ' + ' '.join(steps) + f' pure Reply {TAG} nil }}',
            f'def seeded : Client Reply := do {{ _ <- inv Reply {TAG} seedScript; r <- inv Reply {TAG} {entry}Script; ' +
            (f'_ <- inv Reply {TAG} clearScript; ' if entry == 'retained' else f'_ <- inv Reply {TAG} laterScript; ' if entry == 'nilRetained' else '') + 'done Reply r }']
    return '\n'.join(declarations) + '\n'


def wire(value, kind):
    if kind == 'null':
        return b'null'
    if kind == 'array':
        return ('array:[' + ','.join('bulk:' + v.hex() for v in value) + ']').encode()
    return kind.encode() + b':' + value.hex().encode()


def emit(work, path, entry):
    output = work / ('out-' + entry)
    run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(output)])
    scripts = json.loads((output / 'scripts.json').read_text())
    for script in scripts:
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(not body.startswith(b'#!lua flags=no-writes\n'), 'LIST-MOVE write classification')
        if script['entry'] == entry + 'Script':
            expected_keys = [KEYS[0]] if entry.startswith('same') else sorted(KEYS)
            require(script['keys'] == expected_keys, 'LIST-MOVE declared keys')
    return output


def twin(work, output, row):
    entry, left, right, expected, after_left, after_right, kind = row
    scripts = {s['entry']: s for s in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = ['{path=' + literal(output / (scripts[name]['stem'] + '.lua')) + ',keys={' +
             ','.join(literal(k) for k in scripts[name]['keys']) + '}}' for name in plan['invokes']]
    values, lists, sets, checks, deadlines, expiries = ['other="kept"'], [], [], ['{key="other",value="kept"}'], [], []
    for key, before, after, deadline in zip(KEYS, (left, right), (after_left, after_right), DEADLINES):
        prefix = '[' + literal(key) + ']='
        if isinstance(before, list):
            lists.append(prefix + support.lua_items(before))
        elif isinstance(before, set):
            sets.append(prefix + support.lua_members(before))
        elif isinstance(before, dict):
            values.append(prefix + support.lua_fields(before))
        elif before is not None:
            values.append(prefix + literal(before))
        if before is not None:
            deadlines.append(prefix + literal(deadline))
        expiries.append(prefix + (literal(deadline) if before is not None and after is not None else 'false'))
        check = ('kind="list",items=' + support.lua_items(after) if isinstance(after, list) else
                 'kind="set",members=' + support.lua_members(after) if isinstance(after, set) else
                 'kind="hash",fields=' + support.lua_fields(after) if isinstance(after, dict) else
                 'value=' + ('false' if after is None else literal(after)))
        checks.append('{key=' + literal(key) + ',' + check + '}')
    config = work / 'move-config.lua'
    config.write_text('return {values={' + ','.join(values) + '},lists={' + ','.join(lists) +
        '},sets={' + ','.join(sets) + '},deadlines={' + ','.join(deadlines) + '},expiries={' + ','.join(expiries) +
        '},checks={' + ','.join(checks) + '},invokes={' + ','.join(calls) + '},answer=' + str(plan['answer']) + ',reply=true}\n')
    require(run(['luajit', '-joff', 'dev/lua-store.lua', str(config)]) == wire(expected, kind) + b'\n', 'LIST-MOVE LuaJIT reply')


def refusals(work):
    invalid = []
    good = command('moveLR')
    for side in ('source', 'destination'):
        for redis_type in ('(Str Binary)', 'Hash', 'Set', 'ZSet', 'Stream'):
            invalid.append((good.replace(f'(jobs b"{side}")', '(bad b"wrong")'),
                            f'schema bad : String -> Key {redis_type} tag b"queue"\n'))
        invalid.append((good.replace(f'(jobs b"{side}")', '(bad b"wrong")'),
                        'schema bad : String -> Key List tag b"elsewhere"\n'))
    for endpoint in ('listLeft', 'listRight'):
        invalid.extend((good.replace(endpoint, bad), '') for bad in ('b"LEFT"', 'expiryNX', '(int64 b"0")'))
    for i, (command_text, schema) in enumerate(invalid):
        path, output = work / 'Refused.tet', work / f'refused-{i}'
        path.write_text('module Refused\nschema jobs : String -> Key List tag b"queue"\n' + schema +
            f'def s : Script Reply {TAG} := do {{ r <- {command_text}; pure Reply {TAG} r }}\n' +
            f'def main : Client Reply := do {{ r <- inv Reply {TAG} s; done Reply r }}\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        require(result.returncode == 2 and b'CHECK ' in result.stderr, f'LIST-MOVE refusal {i}: {result.stderr!r}')
        require(not output.exists(), f'LIST-MOVE refusal published output {i}')
    require(len(invalid) == 18, 'LIST-MOVE refusal inventory')
    print('PASS LIST-MOVE-REFUSALS cases=18 atomic_output=18', flush=True)


def live(work, outputs):
    hosts = rejected = errors = expired = 0
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        def args(output, host):
            return ['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)] if host == 'node' else ['/bin/bash', str(output / 'prog.sh')]
        def prepare(left, right):
            run(redis + ['FLUSHDB'])
            run(redis + ['SET', 'other', 'kept'])
            for key, initial, deadline in zip(KEYS, (left, right), DEADLINES):
                if isinstance(initial, (list, set)):
                    for value in initial:
                        op = 'RPUSH' if isinstance(initial, list) else 'SADD'
                        run(redis + ['EVAL', f"return redis.call('{op}',KEYS[1]," + literal(value) + ')', '1', key])
                elif isinstance(initial, dict):
                    for field, value in initial.items():
                        run(redis + ['EVAL', "return redis.call('HSET',KEYS[1]," + literal(field) + ',' + literal(value) + ')', '1', key])
                elif initial in ('zset', 'stream'):
                    run(redis + (['ZADD', key, '1', 'm'] if initial == 'zset' else ['XADD', key, '*', 'f', 'v']))
                elif initial is not None:
                    run(redis + ['-x', 'SET', key], data=initial)
                run(redis + ['PEXPIREAT', key, deadline])
            return [run(redis + ['DUMP', key]) for key in KEYS]
        def state(before, after, dumps):
            for key, original, want, dump, deadline in zip(KEYS, before, after, dumps, DEADLINES):
                if isinstance(want, list):
                    check = ('local got=redis.call("LRANGE",KEYS[1],0,-1); local want=' + support.lua_items(want) +
                             '; if #got ~= #want then return 0 end; for i=1,#want do if got[i] ~= want[i] then return 0 end end; return 1')
                    require(run(redis + ['EVAL', check, '1', key]) == b'1\n', 'LIST-MOVE live complete list order')
                elif want is None:
                    require(run(redis + ['EXISTS', key]) == b'0\n', 'LIST-MOVE missing key')
                else:
                    require(run(redis + ['DUMP', key]) == dump, 'LIST-MOVE error atomicity')
                expiry = '-2' if want is None else '-1' if original is None else deadline
                require(run(redis + ['PEXPIRETIME', key]) == expiry.encode() + b'\n', 'LIST-MOVE expiry')
            require(run(redis + ['GET', 'other']) == b'kept\n', 'LIST-MOVE unrelated state')
        rows = cases() + [('moveLR', wrong, [b'x'], support.WRONG, wrong, [b'x'], 'status') for wrong in ('zset', 'stream')] + [
            ('moveLR', [b'a'], wrong, support.WRONG, [b'a'], wrong, 'status') for wrong in ('zset', 'stream')]
        for entry, left, right, expected, after_left, after_right, kind in rows:
            for host in ('node', 'bash'):
                dumps = prepare(left, right)
                try:
                    wanted = (json.dumps([v.decode('utf-8') for v in expected], ensure_ascii=False, separators=(',', ':')).encode() if kind == 'array' else
                              b'' if expected is None else expected.decode('utf-8').encode()) + b'\n'
                    code = 0
                except UnicodeDecodeError:
                    wanted, code = b'', 4
                actual = run(args(outputs[entry], host), env=env, code=code)
                require(actual == wanted, f'LIST-MOVE {host} {entry} reply: {actual!r} != {wanted!r}')
                state((left, right), (after_left, after_right), dumps)
                hosts, rejected = hosts + 1, rejected + int(code != 0)
        for left, right in [(b'wrong', [b'x']), ([b'a'], b'wrong')]:
            for host in ('node', 'bash'):
                dumps = prepare(left, right)
                require(run(args(outputs['raw'], host), env=env, code=4) == b'', 'LIST-MOVE unhandled error stdout')
                state((left, right), (left, right), dumps)
                errors += 1
        for left, right, expired_key, expected, after in [([b'a'], [b'x'], 0, b'\n', (None, [b'x'])),
                (b'wrong', [b'x'], 0, b'\n', (None, [b'x'])), ([b'a'], b'wrong', 1, b'a\n', (None, [b'a']))]:
            for host in ('node', 'bash'):
                dumps = prepare(left, right)
                run(redis + ['PEXPIREAT', KEYS[expired_key], '1'])
                before = (None, right) if expired_key == 0 else (left, None)
                require(run(args(outputs['moveLR'], host), env=env) == expected, 'LIST-MOVE expired reply')
                state(before, after, dumps)
                expired += 1
        require((len(rows), hosts, rejected, errors, expired) == (52, 104, 2, 4, 6), 'LIST-MOVE live inventory')
        print('PASS LIST-MOVE-E2E cases=52 hosts=104 utf8_refusals=2 errors=4 expired=6', flush=True)
        for entry, expected in EXAMPLES.items():
            for host in ('node', 'bash', 'luajit'):
                run(redis + ['FLUSHDB'])
                actual = run(['./tether', 'exec', 'examples/QueueTransfer.tet', '--entry', entry, '--host', host], env=env)
                require(actual == expected, f'LIST-MOVE example {entry} {host}: {actual!r}')
        print('PASS LIST-MOVE-EXAMPLE exec=9', flush=True)


def main():
    with tempfile.TemporaryDirectory(prefix='tether-list-move-') as temporary:
        work = Path(temporary)
        path = work / 'ListMoveCases.tet'
        path.write_text(source())
        if len(sys.argv) == 3 and sys.argv[1] == '--probe':
            entry = sys.argv[2]
            output = emit(work, path, entry)
            for row in cases():
                if row[0] == entry:
                    twin(work, output, row)
            print('PASS LIST-MOVE-PROBE ' + entry)
            return
        require(len(sys.argv) == 1, 'LIST-MOVE arguments')
        outputs = {entry: emit(work, path, entry) for entry in ENTRIES}
        print('PASS LIST-MOVE-ARTIFACTS pairs=14', flush=True)
        refusals(work)
        for i, row in enumerate(cases()):
            twin(work, outputs[row[0]], row)
            path.write_text(source(row))
            seed_key, seed_value = 'other', 'kept'
            for key, initial in zip(KEYS, row[1:3]):
                if isinstance(initial, (bytes, dict, set)):
                    seed_key, seed_value = key, initial.decode() if isinstance(initial, bytes) else '@hash' if isinstance(initial, dict) else '@set'
            received = []
            code = support.checker.check(work, 'ListMoveCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
                'ListMoveCases.tet', 'seeded', seed_key, seed_value, '1000000'], receive=received.append)
            require(code == 0 and received == [b'REPLY ' + wire(row[3], row[6]) + b'\n'], f'LIST-MOVE store reply {i}: {received!r}')
        print('PASS LIST-MOVE-ORACLES store=48 luajit=48', flush=True)
        live(work, outputs)
    print('PASS LIST-MOVE-TESTS', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, AssertionError, subprocess.SubprocessError, ValueError) as error:
        print('FAIL LIST-MOVE ' + str(error), file=sys.stderr)
        raise SystemExit(1)
