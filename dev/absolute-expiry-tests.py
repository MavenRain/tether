#!/usr/bin/env python3
"""Absolute expiry typing, timestamp boundaries and independent host parity."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('absolute_support', ROOT / 'dev/ttl-tests.py')
ttl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ttl)
run, require, command = ttl.run, ttl.require, ttl.command
SECONDS, MILLIS = 4102444800, 4102444800000


def cases():
    set_value = f'set Reply {ttl.TAG} (items b"x") b"value"'
    at = lambda amount: command('expireat', amount)
    pat = lambda amount: command('pexpireat', amount)
    et, pet = command('expiretime'), command('pexpiretime')
    rows = {}

    def add(name, steps, expected, **options):
        rows[name] = dict(steps=steps, expected=expected, kind='(Str Binary)',
                          seed='@missing', reply='bulk', **options)

    for name, operation, expected in [('atMissing', at(SECONDS), b'0'),
            ('patMissing', pat(MILLIS), b'0'), ('timeMissing', et, b'-2'),
            ('ptimeMissing', pet, b'-2')]:
        add(name, [operation], expected)
    add('persistentSeconds', [set_value, et], b'-1')
    add('persistentMillis', [set_value, pet], b'-1')
    add('secondsResult', [set_value, at(SECONDS)], b'1', deadline=str(MILLIS))
    add('millisResult', [set_value, pat(MILLIS)], b'1', deadline=str(MILLIS))
    add('seconds', [set_value, at(SECONDS), et], str(SECONDS).encode(), deadline=str(MILLIS))
    add('millis', [set_value, pat(MILLIS + 123), pet], str(MILLIS + 123).encode(), deadline=str(MILLIS + 123))
    for offset, rounded in [(499, 0), (500, 1), (1500, 2)]:
        add('round' + str(offset), [set_value, pat(MILLIS + offset), et], str(SECONDS + rounded).encode())
    for name, operation in [('zero', pat(0)), ('negative', pat(-1)),
            ('minimum', pat('-9223372036854775808')), ('zeroSeconds', at(0)), ('negativeSeconds', at(-1))]:
        add(name, [set_value, operation, pet], b'-2', deadline=False)
    add('persisted', [set_value, at(SECONDS), command('persist'), et], b'-1', deadline=False)
    add('overwritten', [set_value, at(SECONDS), set_value, pet], b'-1', deadline=False)
    add('retained', [set_value, pat(MILLIS + 123), pet, command('del')],
        str(MILLIS + 123).encode(), answer=2, deadline=False)
    add('later', [set_value, pat(MILLIS + 123), pet], str(MILLIS + 123).encode(), later=True, deadline=False)
    add('typed', [set_value, at(SECONDS), et], b'integer', classify=True)
    rows['typed']['reply'] = 'status'
    add('maxExact', [set_value, pat('9007199254740991'), pet], b'9007199254740991')
    for name, amount in [('inexactEven', '9007199254740992'), ('inexactOdd', '9007199254740993')]:
        add(name, [set_value, pat(amount), pet], ttl.RANGE, deadline=amount)
        rows[name]['reply'] = 'status'
    for name, amount in [('overflow', '9223372036854776'), ('negativeOverflow', '-9223372036854776')]:
        add(name, [at(amount)], b"ERR invalid expire time in 'expireat' command")
        rows[name]['reply'] = 'status'
    add('raw', [set_value, pat('9007199254740993'), pet], ttl.RANGE, raw=True, later=True)
    for kind, seed in [('(Str Binary)', 'seed'), ('(Str Int64)', '7'), ('Hash', '@hash'),
                       ('List', '@list'), ('Set', '@set'), ('ZSet', '@zset'), ('Stream', '@stream')]:
        name = 'type' + seed.replace('@', '').replace('7', 'Int64')
        add(name, [command('pexpireat', MILLIS, kind), command('expiretime', kind=kind)], str(SECONDS).encode())
        rows[name].update(kind=kind, seed=seed, deadline=str(MILLIS))
    add('replaced', [set_value, at(SECONDS), pat(MILLIS + 2000), pet], str(MILLIS + 2000).encode(), deadline=str(MILLIS + 2000))
    add('relativeThenAbsolute', [set_value, command('expire', 10), pat(MILLIS), pet], str(MILLIS).encode(), deadline=str(MILLIS))
    return rows


def clocks(work):
    row = dict(cases()['millis'], steps=[f'set Reply {ttl.TAG} (items b"x") b"value"',
               command('pexpireat', 1500), command('pexpiretime')], expected=b'1500', deadline='1500')
    output = ttl.emit(work, 'clock-base', row)
    stores, scenarios = ttl.store(work, row, now='1000'), 1
    ttl.twin(work, output, row, advance={0: '1000'})
    text, _main = ttl.source(row).split('def main :', 1)
    text += f'def readLater : Script Reply {ttl.TAG} := do {{ r <- {command("pexpiretime")}; pure Reply {ttl.TAG} r }}\n'
    text += f'def main : Client Reply := do {{ _ <- inv Reply {ttl.TAG} operation; r <- inv Reply {ttl.TAG} readLater; done Reply r }}\n'
    (work / 'TtlCases.tet').write_text(text)
    output = work / 'clock-advance'
    run(['./tether', 'emit', str(work / 'TtlCases.tet'), '-o', str(output)])
    for elapsed, expected, deadline in [('499', b'1500', '1500'), ('500', b'1500', '1500'), ('501', b'-2', False)]:
        ttl.twin(work, output, dict(row, expected=expected, deadline=deadline), advance={0: '1000', 1: elapsed})
        scenarios += 1
    for stamp in (999, 1000):
        expired = dict(row, steps=[row['steps'][0], command('pexpireat', stamp), command('pexpiretime')], expected=b'-2', deadline=False)
        output = ttl.emit(work, 'past-' + str(stamp), expired)
        stores += ttl.store(work, expired, now='1000')
        ttl.twin(work, output, expired, advance={0: '1000'})
        scenarios += 1
    print(f'PASS ABSOLUTE-CLOCK cases={scenarios} store={stores}', flush=True)


def refusals(work):
    original = ttl.source(cases()['seconds'])
    canonical = b'INT64 expected a canonical signed 64-bit decimal'
    changes = [('(int64 b"4102444800")', 'b"4102444800"', b'CHECK unbound: bytesCons is not a constructor of Signed64'),
               ('expireat Reply (Str Binary)', 'expireat Reply Hash', b'the type asks for (In SMu RedisType [] (ACtor Hash) [])'),
               ('expireat Reply (Str Binary) (tag b"ttl")', 'expireat Reply (Str Binary) (tag b"wrong")', b'gives the index (In SMu Tag'),
               ('(int64 b"4102444800")', '(int64 b"01")', canonical),
               ('(int64 b"4102444800")', '(int64 b"9223372036854775808")', canonical),
               ('expiretime Reply (Str Binary)', 'expiretime Reply Hash', b'the type asks for (In SMu RedisType [] (ACtor Hash) [])')]
    for index, (old, new, diagnostic) in enumerate(changes):
        path, output = work / 'TtlCases.tet', work / f'refused-{index}'
        require(original.count(old) == 1, 'ABSOLUTE refusal anchor')
        path.write_text(original.replace(old, new, 1))
        output.mkdir()
        (output / 'keep').write_bytes(b'unchanged')
        result = subprocess.run(['./tether', 'emit', str(path), '-o', str(output)], cwd=ROOT, capture_output=True)
        require(result.returncode == 2 and diagnostic in result.stderr, f'ABSOLUTE typed refusal {index}: {result.stderr!r}')
        require(list(output.iterdir()) == [output / 'keep'] and (output / 'keep').read_bytes() == b'unchanged', 'ABSOLUTE atomic refused output')
    print(f'PASS ABSOLUTE-REFUSALS cases={len(changes)}', flush=True)


def main():
    probe = len(sys.argv) == 3 and sys.argv[1] == '--probe'
    require(probe or sys.argv[1:] in ([], ['--offline']), 'Usage: absolute-expiry-tests.py [--offline|--probe NAME]')
    rows = cases()
    require(len(rows) == 38, f'ABSOLUTE case inventory {len(rows)}')
    if probe and sys.argv[2] == 'clock':
        with tempfile.TemporaryDirectory(prefix='tether-absolute-clock-') as directory:
            clocks(Path(directory))
        print('PASS ABSOLUTE-PROBE clock', flush=True)
        return
    if probe:
        rows = {sys.argv[2]: rows[sys.argv[2]]}
    with tempfile.TemporaryDirectory(prefix='tether-absolute-') as directory:
        work, outputs, stores, twins = Path(directory), {}, 0, 0
        for name, row in rows.items():
            outputs[name] = ttl.emit(work, name, row)
            stores += ttl.store(work, row)
            twins += ttl.twin(work, outputs[name], row)
        if probe:
            print('PASS ABSOLUTE-PROBE ' + sys.argv[2], flush=True)
            return
        print(f'PASS ABSOLUTE-ORACLES store={stores} luajit={twins}', flush=True)
        clocks(work)
        refusals(work)
        if not sys.argv[1:]:
            ttl.live(work, outputs, rows, expected_hosts=76, label='ABSOLUTE')
            hosts = ('node', 'bash', 'luajit')
            for host in hosts:
                require(run(['./tether', 'exec', 'examples/SessionDeadline.tet', '--host', host]) == b'4102444800\n', 'ABSOLUTE example ' + host)
            print(f'PASS ABSOLUTE-EXAMPLE hosts={len(hosts)}', flush=True)
    print('PASS ABSOLUTE-TESTS' + (' offline' if sys.argv[1:] else ''), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f'FAIL ABSOLUTE-TESTS {error}', file=sys.stderr)
        sys.exit(1)
