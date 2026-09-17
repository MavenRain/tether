#!/usr/bin/env python3
"""Conditional expiry truth tables, exact deadlines and live host effects."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('conditional_support', ROOT / 'dev/ttl-tests.py')
ttl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ttl)
run, require, command = ttl.run, ttl.require, ttl.command
SET = f'set Reply {ttl.TAG} (items b"x") b"value"'
COMMANDS = ('expireIf', 'pexpireIf', 'expireatIf', 'pexpireatIf')
CONDITIONS = ('NX', 'XX', 'GT', 'LT')
FUTURE = 4102444800000


def conditional(name, amount, condition, kind='(Str Binary)'):
    return command(name, amount, kind) + ' expiry' + condition


def cases():
    rows = {}

    def add(name, steps, expected, **options):
        rows[name] = dict(steps=steps, expected=str(expected).encode(), kind='(Str Binary)',
                          seed='@missing', reply='bulk', **options)

    for name in COMMANDS:
        seconds, absolute = not name.startswith('p'), 'at' in name
        baseline = FUTURE if absolute else 40000
        amount = lambda ms: ms // 1000 if seconds else ms
        initial = command(name[:-2], amount(baseline))
        for state in ('missing', 'persistent', 'lower', 'equal', 'higher'):
            proposed = baseline + {'lower': -10000, 'higher': 10000}.get(state, 0)
            volatile = state in ('lower', 'equal', 'higher')
            for condition in CONDITIONS:
                accepted = state != 'missing' and (
                    (not volatile and condition in ('NX', 'LT')) or
                    (volatile and (condition == 'XX' or
                                   condition == 'GT' and state == 'higher' or
                                   condition == 'LT' and state == 'lower')))
                steps = ([] if state == 'missing' else [SET]) + ([initial] if volatile else [])
                steps += [conditional(name, amount(proposed), condition)]
                deadline = str(proposed if accepted else baseline) if volatile or accepted else False
                add(name + state + condition, steps, int(accepted), deadline=deadline,
                    relative=not absolute, present=state != 'missing')
        for condition in CONDITIONS:
            accepted = condition in ('XX', 'LT')
            add(name + 'zero' + condition, [SET, initial, conditional(name, 0, condition)],
                int(accepted), deadline=False if accepted else str(baseline),
                relative=not absolute, present=not accepted)
    for name in ('expireIf', 'expireatIf'):
        for condition in CONDITIONS:
            add(name + 'overflow' + condition, [conditional(name, '9223372036854776', condition)],
                f"ERR invalid expire time in '{name[:-2]}' command", deadline=False, present=False)
            rows[name + 'overflow' + condition]['reply'] = 'status'
    large = command('pexpireat', '9007199254740992')
    add('exactAdjacentGT', [SET, large, conditional('pexpireatIf', '9007199254740993', 'GT')],
        1, deadline='9007199254740993', present=True)
    add('exactEqualLT', [SET, large, conditional('pexpireatIf', '9007199254740992', 'LT')],
        0, deadline='9007199254740992', present=True)
    add('persistentInfinity', [SET, conditional('pexpireatIf', '9223372036854775807', 'GT')],
        0, deadline=False, present=True)
    accepted = conditional('pexpireatIf', FUTURE, 'NX')
    add('retained', [SET, accepted, command('del')], 1, answer=1, deadline=False, present=False)
    add('later', [SET, accepted], 1, later=True, deadline=False, present=False)
    add('typed', [SET, accepted], 'integer', classify=True, deadline=str(FUTURE), present=True)
    rows['typed']['reply'] = 'status'
    add('raw', [SET, conditional('pexpireatIf', '9007199254740993', 'NX'), command('pexpiretime')],
        ttl.RANGE.decode(), raw=True, later=True, deadline='9007199254740993', present=True)
    for kind, seed in [('(Str Binary)', 'seed'), ('(Str Int64)', '7'), ('Hash', '@hash'),
                       ('List', '@list'), ('Set', '@set'), ('ZSet', '@zset'), ('Stream', '@stream')]:
        name = 'type' + seed.replace('@', '')
        add(name, [conditional('pexpireatIf', FUTURE, 'NX', kind),
                   conditional('pexpireatIf', FUTURE + 1000, 'XX', kind),
                   command('pexpiretime', kind=kind)], FUTURE + 1000, deadline=str(FUTURE + 1000), present=True)
        rows[name].update(kind=kind, seed=seed)
    add('persistThenNX', [SET, command('pexpireat', FUTURE), command('persist'), accepted],
        1, deadline=str(FUTURE), present=True)
    add('setThenXX', [SET, command('pexpireat', FUTURE), SET, conditional('pexpireatIf', FUTURE + 1000, 'XX')],
        0, deadline=False, present=True)
    return rows


def clocks(work):
    scenarios, stores = 0, 0
    for name, amount, expected, deadline in [('pexpireIf', 1500, 1, '2500'),
            ('pexpireatIf', 1500, 0, '2000'), ('expireIf', 2, 1, '3000'),
            ('expireatIf', 2, 0, '2000')]:
        row = dict(steps=[SET, command('pexpireat', 2000), conditional(name, amount, 'GT')],
                   expected=str(expected).encode(), kind='(Str Binary)', seed='@missing',
                   reply='bulk', deadline=deadline)
        output = ttl.emit(work, 'clock-' + name, row)
        stores += ttl.store(work, row, now='1000')
        ttl.twin(work, output, row, advance={0: '1000'})
        scenarios += 1
    print(f'PASS CONDITIONAL-CLOCK cases={scenarios} store={stores}', flush=True)


def refusals(work):
    original = ttl.source(cases()['expireIfmissingNX'])
    canonical = b'INT64 expected a canonical signed 64-bit decimal'
    changes = [('expiryNX', 'b"NX"', b'ExpiryCondition'),
               ('expiryNX', 'expiryGT expiryLT', b'CHECK'),
               ('expiryNX', 'nil', b'ExpiryCondition'),
               ('expireIf Reply (Str Binary)', 'expireIf Reply Hash', b'ACtor Hash'),
               ('expireIf Reply (Str Binary) (tag b"ttl")', 'expireIf Reply (Str Binary) (tag b"other")', b'gives the index'),
               ('(int64 b"40")', 'b"40"', b'Signed64'),
               ('(int64 b"40")', '(int64 b"01")', canonical),
               ('(int64 b"40")', '(int64 b"9223372036854775808")', canonical)]
    for index, (old, new, diagnostic) in enumerate(changes):
        path, output = work / 'TtlCases.tet', work / f'refused-{index}'
        require(original.count(old) == 1, 'CONDITIONAL refusal anchor')
        path.write_text(original.replace(old, new, 1))
        output.mkdir()
        (output / 'keep').write_bytes(b'unchanged')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True)
        require(result.returncode == 2 and diagnostic in result.stderr,
                f'CONDITIONAL typed refusal {index}: {result.stderr!r}')
        require(list(output.iterdir()) == [output / 'keep'] and (output / 'keep').read_bytes() == b'unchanged',
                'CONDITIONAL atomic refused output')
    print(f'PASS CONDITIONAL-REFUSALS cases={len(changes)}', flush=True)


def live(work, outputs, rows):
    with ttl.support.local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']

        def now():
            seconds, micros = map(int, run(redis + ['TIME']).splitlines())
            return seconds * 1000 + micros // 1000

        count = 0
        for name, row in rows.items():
            for host in ('node', 'bash'):
                run(redis + ['FLUSHDB'])
                seed = row['seed']
                seeds = {'@hash': ['HSET', ttl.KEY, 'f', 'v'], '@set': ['SADD', ttl.KEY, 'm'],
                         '@list': ['RPUSH', ttl.KEY, 'm'], '@zset': ['ZADD', ttl.KEY, '1', 'm'],
                         '@stream': ['XADD', ttl.KEY, '*', 'f', 'v']}
                if seed != '@missing':
                    run(redis + seeds.get(seed, ['SET', ttl.KEY, seed]))
                before = run(redis + ['DUMP', ttl.KEY]) if seed != '@missing' else None
                output = outputs[name]
                args = ['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)] if host == 'node' else ['/bin/bash', str(output / 'prog.sh')]
                start = now()
                reply = run(args, env=env, code=4 if row.get('raw') else 0)
                end = now()
                require(reply == (b'' if row.get('raw') else row['expected'] + b'\n'), f'CONDITIONAL {host} reply {name}')
                require(run(redis + ['EXISTS', ttl.KEY]) == (b'1\n' if row['present'] else b'0\n'), f'CONDITIONAL live presence {name}')
                actual = int(run(redis + ['PEXPIRETIME', ttl.KEY]))
                expected = row['deadline']
                if expected is False:
                    require(actual == (-1 if row['present'] else -2), f'CONDITIONAL live persistence {name}')
                elif row.get('relative'):
                    require(start + int(expected) <= actual <= end + int(expected), f'CONDITIONAL live relative deadline {name}')
                else:
                    require(actual == int(expected), f'CONDITIONAL live exact deadline {name}: {actual}')
                if row['present']:
                    if before is not None:
                        require(run(redis + ['DUMP', ttl.KEY]) == before, f'CONDITIONAL live payload {name}')
                    else:
                        require(run(redis + ['GET', ttl.KEY]) == b'value\n', f'CONDITIONAL live string {name}')
                count += 1
        require(count == 240, f'CONDITIONAL live inventory {count}')
        print(f'PASS CONDITIONAL-E2E cases={len(rows)} hosts={count}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--offline']), 'Usage: conditional-expiry-tests.py [--offline|--probe NAME]')
    rows = cases()
    require(len(rows) == 120, f'CONDITIONAL case inventory {len(rows)}')
    if probe:
        rows = {} if sys.argv[2] == 'clock' else {sys.argv[2]: rows[sys.argv[2]]}
    with tempfile.TemporaryDirectory(prefix='tether-conditional-') as directory:
        work, outputs, stores, twins = Path(directory), {}, 0, 0
        for name, row in rows.items():
            outputs[name] = ttl.emit(work, name, row)
            stores += ttl.store(work, row)
            twins += ttl.twin(work, outputs[name], row)
        if probe:
            if sys.argv[2] == 'clock':
                clocks(work)
            print('PASS CONDITIONAL-PROBE ' + sys.argv[2], flush=True)
            return
        print(f'PASS CONDITIONAL-ORACLES store={stores} luajit={twins}', flush=True)
        clocks(work)
        refusals(work)
        if not sys.argv[1:]:
            live(work, outputs, rows)
            hosts = ('node', 'bash', 'luajit')
            for host in hosts:
                require(run(['./tether', 'exec', 'examples/SessionRenewal.tet', '--host', host]) == b'600\n', 'CONDITIONAL example ' + host)
            print(f'PASS CONDITIONAL-EXAMPLE hosts={len(hosts)}', flush=True)
    print('PASS CONDITIONAL-TESTS' + (' offline' if sys.argv[1:] else ''), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f'FAIL CONDITIONAL-TESTS {error}', file=sys.stderr)
        sys.exit(1)
