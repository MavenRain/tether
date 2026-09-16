#!/usr/bin/env python3
"""Expiry typing, exact replies, deterministic clocks and Redis parity."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ttl_support', ROOT / 'dev/strings-tests.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
run, require, literal = support.run, support.require, support.literal
TAG, KEY = '(tag b"ttl")', '{ttl}:items:x'
RANGE = b'ERR expiry reply is outside exact integer range'


def command(name, amount=None, kind='(Str Binary)'):
    suffix = '' if amount is None else f' (int64 b"{amount}")'
    return f'{name} Reply {kind} {TAG} (items b"x"){suffix}'


def cases():
    set_value = f'set Reply {TAG} (items b"x") b"value"'
    ttl, pttl, persist = [command(name) for name in ('ttl', 'pttl', 'persist')]
    expire = lambda amount: command('expire', amount)
    pexpire = lambda amount: command('pexpire', amount)
    rows = {}

    def add(name, steps, expected, **options):
        rows[name] = dict(steps=steps, expected=expected, kind='(Str Binary)',
                          seed='@missing', reply='bulk', **options)

    for name, operation, expected in [('ttlMissing', ttl, b'-2'), ('pttlMissing', pttl, b'-2'),
            ('persistMissing', persist, b'0'), ('expireMissing', expire(1), b'0'),
            ('pexpireMissing', pexpire(1), b'0')]:
        add(name, [operation], expected)
    add('persistent', [set_value, ttl], b'-1')
    add('expireResult', [set_value, expire(7)], b'1')
    add('seconds', [set_value, expire(7), ttl], b'7')
    add('millis', [set_value, pexpire(1500), pttl], b'1500')
    for duration, expected in [(499, b'0'), (500, b'1'), (1499, b'1'), (1500, b'2')]:
        add('round' + str(duration), [set_value, pexpire(duration), ttl], expected)
    add('zero', [set_value, expire(0), pttl], b'-2')
    add('negative', [set_value, pexpire(-1), pttl], b'-2')
    add('minimum', [set_value, pexpire('-9223372036854775808'), pttl], b'-2')
    add('persistResult', [set_value, expire(7), persist], b'1')
    add('persisted', [set_value, expire(7), persist, pttl], b'-1')
    add('persistTwice', [set_value, expire(7), persist, persist], b'0')
    add('overwritten', [set_value, expire(7), set_value, pttl], b'-1')
    add('retained', [set_value, pexpire(1500), pttl, command('del')], b'1500', answer=2)
    add('later', [set_value, pexpire(1500), pttl], b'1500', later=True)
    add('typed', [set_value, pexpire(1500), pttl], b'integer', classify=True)
    rows['typed']['reply'] = 'status'
    add('maxExact', [set_value, pexpire('9007199254740991'), pttl], b'9007199254740991')
    add('inexact', [set_value, pexpire('9007199254740993'), pttl], RANGE)
    rows['inexact']['reply'] = 'status'
    for name, amount in [('overflow', '9223372036854776'), ('negativeOverflow', '-9223372036854776')]:
        add(name, [expire(amount)], b"ERR invalid expire time in 'expire' command")
        rows[name]['reply'] = 'status'
    add('raw', [set_value, pexpire('9007199254740993'), pttl], RANGE, raw=True, later=True)
    for kind, seed in [('(Str Binary)', 'seed'), ('(Str Int64)', '7'), ('Hash', '@hash'),
                       ('List', '@list'), ('Set', '@set'), ('ZSet', '@zset'), ('Stream', '@stream')]:
        name = 'type' + seed.replace('@', '').replace('7', 'Int64')
        add(name, [command('pexpire', 1500, kind), command('ttl', kind=kind)], b'2')
        rows[name].update(kind=kind, seed=seed)
    for name, deadline in [('millis', '1500'), ('seconds', '7000'), ('persisted', False),
                           ('overwritten', False), ('zero', False), ('retained', False), ('later', False)]:
        rows[name]['deadline'] = deadline
    return rows


def source(row):
    steps = row['steps']
    answer = f'r{row.get("answer", len(steps) - 1)}'
    if row.get('classify'):
        answer = 'classify ' + answer
    elif not row.get('raw'):
        answer = 'expose ' + answer
    body = ' '.join(f'r{i} <- {step};' for i, step in enumerate(steps))
    later = f'_ <- inv Reply {TAG} dropScript; ' if row.get('later') else ''
    return '\n'.join(['module TtlCases', f'schema items : String -> Key {row["kind"]} tag b"ttl"',
        'def expose : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| nil => nil | int n => int n | bulk b => bulk b | status b => status b | err b => status b | array rs => array rs',
        'def classify : Reply -> Reply := fun (r : Reply) => case r as x in Reply return Reply with',
        '| int n => status b"integer" | nil => nil | bulk b => bulk b | status b => status b | err b => status b | array rs => array rs',
        f'def operation : Script Reply {TAG} := do {{ {body} pure Reply {TAG} ({answer}) }}',
        f'def dropScript : Script Reply {TAG} := do {{ _ <- {command("del", kind=row["kind"])}; pure Reply {TAG} nil }}',
        f'def main : Client Reply := do {{ r <- inv Reply {TAG} operation; {later}done Reply r }}', ''])


def emit(work, name, row):
    path, output = work / 'TtlCases.tet', work / name
    path.write_text(source(row))
    run(['./tether', 'emit', str(path), '-o', str(output)])
    require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'TTL canonical bodies')
    readonly = all(step.split()[0] in ('ttl', 'pttl') for step in row['steps'])
    for script in json.loads((output / 'scripts.json').read_text()):
        body = (output / (script['stem'] + '.lua')).read_bytes()
        require(script['keys'] == [KEY], 'TTL declared key')
        require(body.startswith(b'#!lua flags=no-writes\n') == (readonly and script['entry'] == 'operation'),
                'TTL write classification')
    return output


def store(work, row):
    if row.get('raw'):
        return 0
    replies = []
    code = support.checker.check(work, 'TtlCases.tet', command=[str(ROOT / '_build/default/dev/store_run.exe'),
        'TtlCases.tet', 'main', KEY, row['seed'], '1000000'], receive=replies.append)
    kind = b'status' if row['reply'] == 'status' else b'int'
    require(code == 0 and replies == [b'REPLY ' + kind + b':' + row['expected'].hex().encode() + b'\n'],
            f'TTL interpreter reply {replies!r}')
    return 1


def twin(work, output, row, advance=None):
    scripts = {s['entry']: s for s in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = ['{path=' + literal(output / (scripts[name]['stem'] + '.lua')) + ',keys={' + literal(KEY) +
             '},advance=' + literal((advance or {}).get(i, '0')) + '}' for i, name in enumerate(plan['invokes'])]
    seed = row['seed']
    values, sets, lists = '', '', ''
    binding = '[' + literal(KEY) + ']='
    if seed == '@hash':
        values = binding + '{f="v"}'
    elif seed == '@set':
        sets = binding + '{m=true}'
    elif seed == '@list':
        lists = binding + '{"m"}'
    elif seed != '@missing':
        values = binding + literal(seed)
    config = work / 'ttl-config.lua'
    expiries = '' if 'deadline' not in row else binding + ('false' if row['deadline'] is False else literal(row['deadline']))
    config.write_text('return {values={' + values + '},sets={' + sets + '},lists={' + lists +
        '},invokes={' + ','.join(calls) + '},answer=' + str(plan['answer']) + ',kind=' +
        literal('status' if row['reply'] == 'status' else 'string') + ',reply=true,expiries={' + expiries + '}}\n')
    if row.get('raw'):
        result = subprocess.run(['luajit', '-joff', 'dev/lua-store.lua', str(config)], cwd=ROOT, capture_output=True)
        require(result.returncode != 0 and RANGE in result.stderr, 'TTL twin uncaught error')
    else:
        expected = row['reply'].encode() + b':' + row['expected'].hex().encode() + b'\n'
        require(run(['luajit', '-joff', 'dev/lua-store.lua', str(config)]) == expected, 'TTL LuaJIT reply')
    return 1


def clocks(work):
    row = cases()['millis']
    text = source(row)
    before, _main = text.split('def main :', 1)
    text = before + f'def readLater : Script Reply {TAG} := do {{ r <- {command("pttl")}; pure Reply {TAG} r }}\n' + \
        f'def main : Client Reply := do {{ _ <- inv Reply {TAG} operation; r <- inv Reply {TAG} readLater; done Reply r }}\n'
    path, output = work / 'TtlCases.tet', work / 'clock'
    path.write_text(text)
    run(['./tether', 'emit', str(path), '-o', str(output)])
    steps = [('1001', b'499', '1500'), ('1500', b'0', '1500'), ('1501', b'-2', False)]
    for elapsed, expected, deadline in steps:
        twin(work, output, dict(row, expected=expected, deadline=deadline), advance={1: elapsed})
    print(f'PASS TTL-CLOCK cases={len(steps)}', flush=True)


def refusals(work):
    base = cases()['seconds']
    original = source(base)
    canonical = b'INT64 expected a canonical signed 64-bit decimal'
    changes = [('(int64 b"7")', 'b"7"', b'CHECK unbound: bytesCons is not a constructor of Signed64'),
               ('expire Reply (Str Binary)', 'expire Reply Hash',
                b'the type asks for (In SMu RedisType [] (ACtor Hash) [])'),
               ('expire Reply (Str Binary) (tag b"ttl")', 'expire Reply (Str Binary) (tag b"wrong")',
                b'gives the index (In SMu Tag'),
               ('(int64 b"7")', '(int64 b"01")', canonical),
               ('(int64 b"7")', '(int64 b"9223372036854775808")', canonical)]
    require(len(changes) == 5, 'TTL refusal inventory')
    for index, (old, new, diagnostic) in enumerate(changes):
        path, output = work / 'TtlCases.tet', work / f'refused-{index}'
        require(old in original, 'TTL refusal anchor')
        path.write_text(original.replace(old, new, 1))
        output.mkdir()
        (output / 'keep').write_bytes(b'unchanged')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True)
        require(result.returncode == 2 and diagnostic in result.stderr,
                f'TTL typed refusal {index}: {result.returncode} {result.stdout!r} {result.stderr!r}')
        require(list(output.iterdir()) == [output / 'keep'] and (output / 'keep').read_bytes() == b'unchanged',
                'TTL atomic refused output')
    print(f'PASS TTL-REFUSALS cases={len(changes)}', flush=True)


def live(work, outputs, rows):
    with support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']
        count = 0
        for name, row in rows.items():
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                seed = row['seed']
                seeds = {'@hash': ['HSET', KEY, 'f', 'v'], '@set': ['SADD', KEY, 'm'],
                         '@list': ['RPUSH', KEY, 'm'], '@zset': ['ZADD', KEY, '1', 'm'],
                         '@stream': ['XADD', KEY, '*', 'f', 'v']}
                if seed != '@missing':
                    run(redis + seeds.get(seed, ['SET', KEY, seed]))
                output = outputs[name]
                args = ['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)] if host == 'node' else ['/bin/bash', str(output / 'prog.sh')]
                if row.get('raw'):
                    require(run(args, env=env, code=4) == b'', 'TTL uncaught error stops host')
                    require(run(redis + ['EXISTS', KEY]) == b'1\n', 'TTL error stops later invocation')
                else:
                    require(run(args, env=env) == row['expected'] + b'\n', f'TTL {host} reply {name}')
                count += 1
        require(count == 70, f'TTL live inventory {count}')
        print(f'PASS TTL-E2E cases={len(rows)} hosts={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--offline']), 'Usage: ttl-tests.py [--offline|--probe NAME]')
    rows = cases()
    require(len(rows) == 35, f'TTL case inventory {len(rows)}')
    if probe:
        rows = {sys.argv[2]: rows[sys.argv[2]]}
    with tempfile.TemporaryDirectory(prefix='tether-ttl-') as directory:
        work, outputs, stores, twins = Path(directory), {}, 0, 0
        for name, row in rows.items():
            outputs[name] = emit(work, name, row)
            stores += store(work, row)
            twins += twin(work, outputs[name], row)
        if probe:
            print('PASS TTL-PROBE ' + sys.argv[2], flush=True)
            return
        print(f'PASS TTL-ORACLES store={stores} luajit={twins}', flush=True)
        clocks(work)
        refusals(work)
        if not sys.argv[1:]:
            live(work, outputs, rows)
            hosts = ('node', 'bash', 'luajit')
            for host in hosts:
                require(run(['./tether', 'exec', 'examples/SessionLease.tet', '--host', host]) == b'300\n', 'TTL example ' + host)
            print(f'PASS TTL-EXAMPLE hosts={len(hosts)}', flush=True)
    print('PASS TTL-TESTS' + (' offline' if sys.argv[1:] else ''), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f'FAIL TTL-TESTS {error}', file=sys.stderr)
        sys.exit(1)
