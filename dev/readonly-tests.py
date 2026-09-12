#!/usr/bin/env python3
"""Read-only dispatch transcripts and independently checked localhost execution."""
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
KEY = '{counter}:hits:visits'


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


shell = module('ro_shell', 'dev/stage-d-tests.py')
previous = module('ro_previous', 'dev/stage-e-tests.py')
local = module('ro_local', 'bin/local.py')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run(args, env=None):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, env=env, timeout=120)
    require(result.returncode == 0, f'{args}: exit={result.returncode}\n{result.stdout!r}\n{result.stderr!r}')
    return result.stdout


def transcripts(work, outputs):
    bindir = work / 'bin'
    bindir.mkdir()
    stub = bindir / 'curl'
    stub.write_text('#!/bin/sh\nexec ' + shlex.join([sys.executable, '-P',
                    str(ROOT / 'dev/stage-d-tests.py'), '--curl']) + ' "$@"\n')
    stub.chmod(0o755)
    load = {'auto_sha': True}
    # Every counter in the row below is the number of transcripts this run made.
    fallback = mixed = faults = 0
    for missing in ('NOSCRIPT', 'NOSCRIPT No matching script.'):
        calls = shell.exercise(work, outputs['twice'],
            [load, {'error': missing}, {'result': '9007199254740993'}, {'result': 'last'}], b'last\n')
        require([c[0] for c in calls] == ['SCRIPT', 'EVALSHA_RO', 'EVAL_RO', 'EVALSHA_RO'], 'RO-SH fallback order')
        require(calls[2][1] == calls[0][2] and calls[2][2:] == calls[1][2:] == ['1', KEY], 'RO-SH fallback bytes')
        fallback += 1
    calls = shell.exercise(work, outputs['mixed'],
        [load, {'result': '1'}, load, {'result': '1'}, {'result': '2'}], b'1\n')
    require([c[0] for c in calls] == ['SCRIPT', 'EVALSHA', 'SCRIPT', 'EVALSHA_RO', 'EVALSHA'], 'RO-SH per-script mode')
    mixed += 1
    for fault in ('NOPERM read-only command', 'NOSCRIPTED', 'ERR embedded NOSCRIPT'):
        calls = shell.exercise(work, outputs['twice'], [load, {'error': fault}], code=4,
                               stderr=(fault + '\n').encode())
        require([c[0] for c in calls] == ['SCRIPT', 'EVALSHA_RO'], 'RO-SH unexpected retry')
        faults += 1
    calls = shell.exercise(work, outputs['twice'],
        [load, {'error': 'NOSCRIPT'}, {'error': 'NOSCRIPT'}], code=4, stderr=b'NOSCRIPT\n')
    require([c[0] for c in calls] == ['SCRIPT', 'EVALSHA_RO', 'EVAL_RO'], 'RO-SH retry limit')
    faults += 1
    print(f'PASS RO-SH fallback={fallback} mixed={mixed} faults={faults}', flush=True)


def live(work, outputs):
    with local.hosts(work) as (port, env):
        redis = ['redis-cli', '-h', '127.0.0.1', '-p', str(port), '--raw']

        def command(*args):
            return run(redis + list(args))

        def commandstats():
            counts = {}
            for row in command('INFO', 'commandstats').decode('utf-8', 'replace').splitlines():
                name, _, rest = row[len('cmdstat_'):].partition(':')
                if row.startswith('cmdstat_') and 'calls=' in rest:
                    counts[name] = int(rest.split('calls=')[1].split(',')[0])
            return counts

        require(command('ACL', 'SETUSER', 'default', '-eval', '-evalsha') == b'OK\n', 'ACL setup')
        require(b'NOPERM' in command('EVAL', 'return 1', '0'), 'ACL negative control')
        # Neither host sends EVAL in steady state, so the EVALSHA restriction
        # needs its own control before it can police a wrong suffix.
        require(b'NOPERM' in command('EVALSHA', '0' * 40, '0'), 'ACL evalsha control')
        cases = store = luajit = 0
        for entry in ('main', 'twice'):
            output = outputs[entry]
            for initial in (None, '9007199254740993', '-9223372036854775808'):
                expected = b'\n' if initial is None else initial.encode() + b'\n'
                require(previous.store_run('ReadOnly.tet', entry, initial)[1] == expected, 'RO store')
                store += 1
                require(previous.lua_run(work, output, initial) == expected, 'RO LuaJIT')
                luajit += 1
                for host in ('node', 'bash'):
                    require(command('DEL', KEY) in (b'0\n', b'1\n'), 'DEL fixture')
                    if initial is not None:
                        require(command('SET', KEY, initial) == b'OK\n', 'SET fixture')
                    log = work / 'requests.jsonl'
                    log.unlink(missing_ok=True)
                    args = (['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)]
                            if host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                    invokes = 1 if entry == 'main' else 2
                    before = commandstats() if host == 'node' else {}
                    require(run(args, env=env) == expected, 'RO artifact stdout')
                    after = commandstats() if host == 'node' else {}
                    require(command('GET', KEY) == expected, 'RO changed stored value')
                    require(command('EXISTS', KEY) == (b'0\n' if initial is None else b'1\n'), 'RO created missing key')
                    if host == 'bash':
                        calls = [json.loads(row)['command'] for row in log.read_text().splitlines()]
                        require(calls == ['SCRIPT'] + ['EVALSHA_RO'] * (1 if entry == 'main' else 2), 'RO steady calls')
                    else:
                        # The Node host talks straight to Redis, so the server
                        # counters are the record of what it dispatched.
                        delta = {name: after.get(name, 0) - before.get(name, 0)
                                 for name in set(after) | set(before)}
                        loads = delta.get('script|load', delta.get('script', 0))
                        require(delta.get('evalsha_ro', 0) == invokes and loads == 1
                                and not any(delta.get(name, 0) for name in ('eval', 'evalsha', 'eval_ro')),
                                f'RO node steady calls {delta}')
                    cases += 1
        # The child owns this verdict, so the row is re-emitted verbatim.
        child = run(['node', 'dev/readonly-live.mjs', str(outputs['twice']), str(port)])
        verdict = [row for row in child.decode('utf-8', 'replace').splitlines()
                   if row.startswith('PASS RO-LIVE ')]
        require(len(verdict) == 1, f'Missing live fallback verdict {child!r}')
        print(verdict[0], flush=True)
        require(command('ACL', 'SETUSER', 'default', '+eval', '+evalsha') == b'OK\n', 'ACL restore')
        mixed = 0
        for host in ('node', 'bash'):
            command('DEL', KEY)
            args = (['node', 'runtime/redis-host.mjs', str(outputs['mixed'] / 'prog.wasm'), str(port)]
                    if host == 'node' else ['/bin/bash', str(outputs['mixed'] / 'prog.sh')])
            require(run(args, env=env) == b'1\n' and command('GET', KEY) == b'2\n', 'Mixed captured reply and writes')
            mixed += 1
        print(f'PASS RO-E2E acl_readonly={cases} mixed={mixed} store={store} luajit={luajit}', flush=True)


def main():
    require(sys.argv[1:] in ([], ['--shell-only']), 'Usage: readonly-tests.py [--shell-only]')
    with tempfile.TemporaryDirectory(prefix='tether-readonly-') as temporary:
        work = Path(temporary)
        outputs = {entry: work / entry for entry in ('main', 'twice', 'mixed')}
        for entry, output in outputs.items():
            run(['./tether', 'emit', 'examples/ReadOnly.tet', '--entry', entry, '-o', str(output)])
            require(b'LUA-SAME ' in run(['node', 'dev/lua-same.mjs', str(output)]), 'RO canonical Lua bytes')
        transcripts(work, outputs)
        if '--shell-only' not in sys.argv:
            live(work, outputs)
    print('PASS RO-TESTS', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL RO-TESTS {error}', file=sys.stderr)
        sys.exit(1)
