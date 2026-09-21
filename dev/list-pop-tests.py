#!/usr/bin/env python3
"""Counted pops: replies, ordered state, expiries and captured values on every host."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pop_support', ROOT / 'dev/lists-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, tet, literal = support.run, support.require, support.tet, support.literal
TAG, KEY, DEADLINE = '(tag b"queue")', '{queue}:jobs:mail', '4102444800000'
NEGATIVE = b'ERR value is out of range, must be positive'
COUNTS = {'Zero': '0', 'One': '1', 'Two': '2', 'All': '9',
          'Max': '9223372036854775807', 'Negative': '-1', 'Min': '-9223372036854775808'}
COMMANDS = {side + name: (op, count) for side, op in [('left', 'lpopMany'), ('right', 'rpopMany')]
            for name, count in COUNTS.items()}
COMMANDS.update({name: ('lpopMany', '2') for name in ('computed', 'within', 'retained', 'nilRetained', 'raw')})
EXAMPLES = {'main': b'["welcome:alice","welcome:bob"]\n', 'retained': b'["welcome:alice","welcome:bob"]\n',
            'remaining': b'["welcome:carol"]\n', 'newest': b'["welcome:carol","welcome:bob"]\n'}


def command(entry):
    op, count = COMMANDS[entry]
    value = f'(int64 b"{count}")'
    if entry == 'computed':
        value = f'(countIdentity {value})'
    return f'{op} Reply {TAG} (jobs b"mail") {value}'


def cases():
    rows = []
    for side in ('left', 'right'):
        for name in ('Zero', 'One', 'Two', 'All', 'Max'):
            for before in (None, [b'a'], [b'c', b'a', b'b', b'a']):
                n = min(int(COUNTS[name]), len(before or []))
                ordered = list(before or []) if side == 'left' else list(reversed(before or []))
                rest = ordered[n:] if side == 'left' else list(reversed(ordered[n:]))
                rows.append((side + name, before, ordered[:n] if before else None, rest or None, 'array' if before else 'null'))
        for name in ('Negative', 'Min'):
            rows.extend((side + name, before, NEGATIVE, before, 'status')
                        for before in (None, [b'a', b'b'], b'wrong'))
        for name in ('Zero', 'Two'):
            rows.extend((side + name, before, support.WRONG, before, 'status')
                        for before in (b'wrong', {b'f': b'v'}, {b'm'}))
        for value in (b'', bytes(range(256)), support.TEXT, b'01', b'9007199254740993'):
            rows.append((side + 'Two', [value, b'z'], [value, b'z'] if side == 'left' else [b'z', value], None, 'array'))
    rows += [('computed', [b'c', b'a', b'b'], [b'c', b'a'], [b'b'], 'array'),
             ('within', [b'c', b'a', b'b'], [b'c', b'a'], None, 'array'),
             ('retained', [b'c', b'a', b'b'], [b'c', b'a'], None, 'array'),
             ('nilRetained', None, None, [b'later'], 'null'),
             ('raw', [b'c', b'a', b'b'], [b'c', b'a'], [b'b'], 'array')]
    require(len(rows) == 69, 'LIST-POP case inventory')
    return rows


def source(seed=None):
    declarations = ['module ListPopCases', 'schema jobs : String -> Key List tag b"queue"',
        'def countIdentity : Signed64 -> Signed64 := fun (n : Signed64) => n',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b',
        '| status b => status b | err b => status b | array rs => array rs',
        f'def clearScript : Script Reply {TAG} := do {{ r <- del Reply List {TAG} (jobs b"mail"); pure Reply {TAG} r }}',
        f'def laterScript : Script Reply {TAG} := do {{ r <- rpush Reply {TAG} (jobs b"mail") b"later"; pure Reply {TAG} r }}']
    for entry in COMMANDS:
        after = f'_ <- del Reply List {TAG} (jobs b"mail"); ' if entry == 'within' else ''
        body = (f'{command(entry)} (fun (r : Reply) => pure Reply {TAG} r)' if entry == 'raw' else
                f'do {{ r <- {command(entry)}; {after}pure Reply {TAG} (expose r) }}')
        later = f'_ <- inv Reply {TAG} clearScript; ' if entry == 'retained' else f'_ <- inv Reply {TAG} laterScript; ' if entry == 'nilRetained' else ''
        declarations += [f'def {entry}Script : Script Reply {TAG} := {body}',
            f'def {entry} : Client Reply := do {{ r <- inv Reply {TAG} {entry}Script; {later}done Reply r }}']
    if seed is not None:
        entry, before, *_ = seed
        steps = [f'_ <- rpush Reply {TAG} (jobs b"mail") {tet(v)};' for v in before] if isinstance(before, list) else []
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
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(not body.startswith(b'#!lua flags=no-writes\n'), 'LIST-POP write classification')
        require(script['keys'] == [KEY], 'LIST-POP declared keys')
    return output


def twin(work, output, row):
    entry, before, expected, after, kind = row
    scripts = {s['entry']: s for s in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = ['{path=' + literal(output / (scripts[name]['stem'] + '.lua')) + ',keys={' + literal(KEY) + '}}' for name in plan['invokes']]
    prefix = '[' + literal(KEY) + ']='
    value = support.lua_fields(before) if isinstance(before, dict) else literal(before) if isinstance(before, bytes) else 'nil'
    lists = prefix + support.lua_items(before) if isinstance(before, list) else ''
    sets = prefix + support.lua_members(before) if isinstance(before, set) else ''
    check = ('kind="list",items=' + support.lua_items(after) if isinstance(after, list) else
             'kind="hash",fields=' + support.lua_fields(after) if isinstance(after, dict) else
             'kind="set",members=' + support.lua_members(after) if isinstance(after, set) else
             'value=' + ('false' if after is None else literal(after)))
    expiry = 'false' if after is None or before is None else literal(DEADLINE)
    config = work / 'pop-config.lua'
    config.write_text('return {values={other="kept",' + prefix + value + '},lists={' + lists + '},sets={' + sets +
        '},deadlines={' + (prefix + literal(DEADLINE) if before is not None else '') + '},expiries={' + prefix + expiry +
        '},checks={{key="other",value="kept"},{key=' + literal(KEY) + ',' + check + '}},invokes={' + ','.join(calls) +
        '},answer=' + str(plan['answer']) + ',reply=true}\n')
    require(run(['luajit', '-joff', 'dev/lua-store.lua', str(config)]) == wire(expected, kind) + b'\n', 'LIST-POP LuaJIT reply')


def refusals(work):
    invalid = []
    for op in ('lpopMany', 'rpopMany'):
        good = f'{op} Reply {TAG} (jobs b"mail") (int64 b"2")'
        invalid += [(f'schema jobs : String -> Key {ty} tag b"queue"', good) for ty in ('Hash', 'Set', '(Str Binary)')]
        invalid += [('schema jobs : String -> Key List tag b"other"', good),
                    ('schema jobs : String -> Key List tag b"queue"', good.replace('(int64 b"2")', 'b"2"')),
                    ('schema jobs : String -> Key List tag b"queue"', good.replace('(int64 b"2")', '2')),
                    ('schema jobs : String -> Key List tag b"queue"', good.replace('b"2"', 'b"9223372036854775808"'))]
    for i, (schema, call) in enumerate(invalid):
        path, output = work / 'Bad.tet', work / f'bad-{i}'
        path.write_text(f'module Bad\n{schema}\ndef body : Script Reply {TAG} := do {{ r <- {call}; pure Reply {TAG} r }}\n'
                        f'def main : Client Reply := inv Reply {TAG} body (fun (r : Reply) => done Reply r)\n')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True, timeout=120)
        diagnostic = b'INT64 ' if i % 7 == 6 else b'CHECK '
        require(result.returncode == 2 and diagnostic in result.stderr, f'LIST-POP refusal {i}: code={result.returncode} {result.stderr!r}')
        require(not output.exists(), f'LIST-POP atomic refusal output {i}')
    print('PASS LIST-POP-REFUSALS cases=14 atomic_output=14', flush=True)


def live(work, outputs):
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        def args(output, host):
            return ['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)] if host == 'node' else ['/bin/bash', str(output / 'prog.sh')]
        def prepare(before):
            run(redis + ['FLUSHDB'])
            run(redis + ['SET', 'other', 'kept'])
            if isinstance(before, (list, set)):
                for value in before:
                    op = 'RPUSH' if isinstance(before, list) else 'SADD'
                    run(redis + ['EVAL', f"return redis.call('{op}',KEYS[1]," + literal(value) + ')', '1', KEY])
            elif isinstance(before, dict):
                for field, value in before.items():
                    run(redis + ['EVAL', "return redis.call('HSET',KEYS[1]," + literal(field) + ',' + literal(value) + ')', '1', KEY])
            elif before in ('zset', 'stream'):
                run(redis + (['ZADD', KEY, '1', 'm'] if before == 'zset' else ['XADD', KEY, '*', 'f', 'v']))
            elif before is not None:
                run(redis + ['-x', 'SET', KEY], data=before)
            run(redis + ['PEXPIREAT', KEY, DEADLINE])
            return run(redis + ['DUMP', KEY])
        def state(before, after, dump):
            if isinstance(after, list):
                check = ('local got=redis.call("LRANGE",KEYS[1],0,-1); local want=' + support.lua_items(after) +
                         '; if #got ~= #want then return 0 end; for i=1,#want do if got[i] ~= want[i] then return 0 end end; return 1')
                require(run(redis + ['EVAL', check, '1', KEY]) == b'1\n', 'LIST-POP remaining order')
            elif after is None:
                require(run(redis + ['EXISTS', KEY]) == b'0\n', 'LIST-POP key removal')
            else:
                require(run(redis + ['DUMP', KEY]) == dump, 'LIST-POP error atomicity')
            expiry = '-2' if after is None else '-1' if before is None else DEADLINE
            require(run(redis + ['PEXPIRETIME', KEY]) == expiry.encode() + b'\n', 'LIST-POP expiry')
            require(run(redis + ['GET', 'other']) == b'kept\n', 'LIST-POP unrelated state')
        rows = cases() + [(entry, wrong, support.WRONG, wrong, 'status')
                         for entry in ('leftZero', 'rightTwo') for wrong in ('zset', 'stream')]
        rejected = 0
        for entry, before, expected, after, kind in rows:
            for host in ('node', 'bash'):
                dump = prepare(before)
                try:
                    wanted = (json.dumps([v.decode('utf-8') for v in expected], ensure_ascii=False, separators=(',', ':')).encode()
                              if kind == 'array' else b'' if expected is None else expected.decode('utf-8').encode()) + b'\n'
                    code = 0
                except UnicodeDecodeError:
                    wanted, code = b'', 4
                require(run(args(outputs[entry], host), env=env, code=code) == wanted, f'LIST-POP live {entry} {host}')
                state(before, after, dump)
                rejected += int(code != 0)
        for host in ('node', 'bash'):
            dump = prepare(b'wrong')
            require(run(args(outputs['raw'], host), env=env, code=4) == b'', 'LIST-POP unhandled error stdout')
            state(b'wrong', b'wrong', dump)
            for entry in ('leftZero', 'rightTwo'):
                prepare([b'old'])
                run(redis + ['PEXPIREAT', KEY, '1'])
                require(run(args(outputs[entry], host), env=env) == b'\n', 'LIST-POP expired reply')
                state(None, None, b'')
        require(len(rows) == 73 and rejected == 4, 'LIST-POP live inventory')
        print('PASS LIST-POP-E2E cases=73 hosts=146 utf8_refusals=4 errors=2 expired=4', flush=True)
        for entry, expected in EXAMPLES.items():
            for host in ('node', 'bash', 'luajit'):
                run(redis + ['FLUSHDB'])
                require(run(['./tether', 'exec', 'examples/QueueDrain.tet', '--entry', entry, '--host', host], env=env) == expected,
                        f'LIST-POP example {entry} {host}')
        print('PASS LIST-POP-EXAMPLE exec=12', flush=True)


def main():
    with tempfile.TemporaryDirectory(prefix='tether-list-pop-') as temporary:
        work = Path(temporary)
        path = work / 'ListPopCases.tet'
        path.write_text(source())
        if len(sys.argv) == 3 and sys.argv[1] == '--probe':
            entry = sys.argv[2]
            output = emit(work, path, entry)
            for row in cases():
                if row[0] == entry:
                    twin(work, output, row)
            print('PASS LIST-POP-PROBE ' + entry)
            return
        require(len(sys.argv) == 1, 'LIST-POP arguments')
        outputs = {entry: emit(work, path, entry) for entry in COMMANDS}
        require(len(outputs) == 19, 'LIST-POP artifact inventory')
        print('PASS LIST-POP-ARTIFACTS pairs=19', flush=True)
        refusals(work)
        for i, row in enumerate(cases()):
            twin(work, outputs[row[0]], row)
            path.write_text(source(row))
            before = row[1]
            seed = before.decode() if isinstance(before, bytes) else '@hash' if isinstance(before, dict) else '@set' if isinstance(before, set) else '@missing'
            received = []
            code = support.checker.check(work, path.name, command=[str(ROOT / '_build/default/dev/store_run.exe'),
                path.name, 'seeded', KEY, seed, '1500000'], receive=received.append)
            require(code == 0 and received == [b'REPLY ' + wire(row[2], row[4]) + b'\n'], f'LIST-POP store reply {i}: {received!r}')
        print('PASS LIST-POP-ORACLES store=69 luajit=69', flush=True)
        live(work, outputs)
    print('PASS LIST-POP-TESTS', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, AssertionError, subprocess.SubprocessError, ValueError, KeyError) as error:
        print('FAIL LIST-POP ' + str(error), file=sys.stderr)
        raise SystemExit(1)
