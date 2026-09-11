#!/usr/bin/env python3
"""Driver, compiled Client parity, byte lowering and Stage F mutation controls."""
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


driver = module('tether_driver', 'bin/driver.py')
local = module('tether_local', 'bin/local.py')
previous = module('tether_e', 'dev/stage-e-tests.py')
bench = module('tether_bench', 'dev/m0-bench.py')


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def run(args, code=0, env=None, diagnostic=None):
    child = subprocess.run(args, cwd=ROOT, capture_output=True, env=env, timeout=120)
    require(child.returncode == code, f'{args}: exit={child.returncode}\n{child.stdout!r}\n{child.stderr!r}')
    if diagnostic:
        require(diagnostic in child.stdout + child.stderr, f'Missing diagnostic {diagnostic!r}')
    return child.stdout


def byte_lowering(work):
    for i, sample in enumerate((b'', bytes(range(256)), b'a\x00b\xff\n' * 13)):
        (work / 'Bytes.bin').write_bytes(sample)
        rows = []
        code = previous.checker.check(work, 'Bytes.bin',
            command=[str(ROOT / '_build/default/dev/bytes_probe.exe')], receive=rows.append)
        require(code == 0 and len(rows) == 2, 'Byte lowering compiler')
        for row in rows:
            name, value = row.split()
            wasm = work / f'bytes-{i}-{name.decode()}.wasm'
            wasm.write_bytes(bytes.fromhex(value.decode()))
            require(run(['node', 'dev/extract-body.mjs', str(wasm)]) == sample, 'Byte lowering bytes')
    print('PASS BYTE-LOWERING reference=1 lowered=1 all_bytes=256 empty=1 repeated=1', flush=True)


def reply_parity(work):
    # The Bash host formats an array reply with jq and the Node host with its
    # own serialiser. Byte 0x7F is escaped by jq and not by JSON.stringify, so
    # the three producers are compared on the same fixtures here.
    probe = work / 'reply-probe.mjs'
    probe.write_text('import { replyText } from ' +
                     json.dumps(str(ROOT / 'runtime/redis-host.mjs')) + ';\n'
                     'process.stdout.write(replyText(JSON.parse(process.argv[2])));\n')
    fixtures = [[], ['plain'], ['a\x7fb'], ['\x7f'], ['ÿĀ \t"\\'], ['one', 'a\x7fb', '']]
    seen = 0
    for fixture in fixtures:
        envelope = json.dumps({'result': fixture}).encode()
        child = subprocess.run(['jq', '-c', '.result'], input=envelope, capture_output=True, timeout=30)
        require(child.returncode == 0, f'jq reply {fixture!r}: {child.stderr!r}')
        node = run(['node', str(probe), json.dumps(fixture)])
        row = 'array:[' + ','.join('bulk:' + item.encode().hex() for item in fixture) + ']'
        store = driver.reply_text(row.encode())
        require(child.stdout == node == store,
                f'Array reply {fixture!r}: jq={child.stdout!r} node={node!r} store={store!r}')
        seen += sum(1 for item in fixture if '\x7f' in item)
    require(seen == 3, 'Array reply fixtures lost the DEL byte')
    print(f'PASS REPLY-ARRAY-PARITY cases={len(fixtures)} del_byte=1 producers=3', flush=True)


def main():
    with tempfile.TemporaryDirectory(prefix='tether-f-') as temporary:
        work = Path(temporary)
        byte_lowering(work)
        reply_parity(work)
        entries =[('M0Spine.tet', 'main'), ('ShCases.tet', 'twice'), ('ClientCases.tet', 'earlierOutput'),
                   ('ShCases.tet', 'capturedReply'), ('ShCases.tet', 'exactMain'),
                   ('ShCases.tet', 'stopped'), ('ClientCases.tet', 'afterFault'),
                   ('HostCases.tet', 'readMain'), ('HostCases.tet', 'incrementMain')]
        for source, entry in entries:
            code, _ms = driver.emit(ROOT / 'examples', source, work / entry, entry)
            require(code == 0, f'Emit {entry}')
            print(run(['node', 'dev/lua-same.mjs', str(work / entry)]).decode().strip(), flush=True)
            run(['/bin/bash', '-n', str(work / entry / 'prog.sh')])
        print(run(['node', 'dev/client-tests.mjs', str(work)]).decode().strip(), flush=True)
        with local.hosts(work) as (port, env):
            cli = ['redis-cli', '-h', '127.0.0.1', '-p', str(port)]
            def reset(initial):
                run(cli + ['FLUSHDB'])
                run(cli + ['SCRIPT', 'FLUSH'])
                if initial is not None:
                    run(cli + ['SET', previous.KEY, initial])
            cases = [('main', None, b'1\n'), ('main', '9007199254740992', b'9007199254740993\n'),
                     ('twice', '0', b'2\n'), ('earlierOutput', '0', b'1\n'),
                     ('capturedReply', '0', b'1\n'), ('exactMain', None, b'9007199254740993\n'),
                     ('readMain', None, b'\n'), ('readMain', 'a\nlast\n', b'a\nlast\n\n'),
                     ('readMain', '\ufeffzero\x00tail\n', '\ufeffzero\x00tail\n\n'.encode()),
                     ('incrementMain', '9223372036854775806', b'9223372036854775807\n'),
                     ('incrementMain', '-9223372036854775808', b'-9223372036854775807\n')]
            for entry, initial, expected in cases:
                output = work / entry
                # NUL cannot be an argv byte; use redis-cli -x for that fixture.
                if initial is not None and '\x00' in initial:
                    run(cli + ['FLUSHDB'])
                    subprocess.run(cli + ['-x', 'SET', previous.KEY], input=initial.encode(),
                                   check=True, stdout=subprocess.DEVNULL, timeout=10)
                else:
                    reset(initial)
                node = run(['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)])
                require(node == expected, f'Node {entry}: {node!r}')
                if initial is not None and '\x00' in initial:
                    # JSON preserves NUL inside shell envelope variables.
                    shell = run(['/bin/bash', str(output / 'prog.sh')], env=env)
                else:
                    reset(initial)
                    shell = run(['/bin/bash', str(output / 'prog.sh')], env=env)
                lua = previous.lua_run(work, output, initial)
                require(node == shell == lua, f'E2E {entry}')
                print(f'E2E-3WAY luajit=1 node=1 sh=1 artifact=prog.wasm entry={entry} '
                      f'reply_hex={expected.hex()}', flush=True)
            reset('9223372036854775807')
            run(['node', 'runtime/redis-host.mjs', str(work / 'incrementMain/prog.wasm'), str(port)], code=4)
            require(run(cli + ['GET', previous.KEY]) == b'9223372036854775807\n', 'Overflow changed store')
            reset('0')
            start = len((work / 'requests.jsonl').read_text().splitlines())
            require(run(['/bin/bash', str(work / 'twice/prog.sh')], env=env) == b'2\n', 'Load once output')
            requests = [json.loads(row) for row in (work / 'requests.jsonl').read_text().splitlines()[start:]]
            require([row['command'] for row in requests] == ['SCRIPT', 'EVALSHA', 'EVALSHA'], 'Load once calls')
            loads = [row for row in requests if row['command'] == 'SCRIPT']
            steady = requests[2:]
            require(len(loads) == 1 and len(steady) == 1 and len(requests) == 3,
                    f'Load once counts: {len(loads)} {len(steady)} {len(requests)}')
            print(f'LOAD-ONCE rest_calls={len(loads)} invoke_lines={len(steady)} '
                  f'warmup_calls={len(requests) - len(steady)} total_calls={len(requests)}', flush=True)
        for host in ('node', 'bash', 'luajit'):
            require(run(['./tether', 'exec', 'examples/M0Spine.tet', '--host', host]) == b'1\n', host)
        original_emit = driver.emit
        def appending_emit(suffix):
            def altered(*args):
                result = original_emit(*args)
                if result[0] == 0:
                    with (args[2] / 'prog.sh').open('ab') as stream:
                        stream.write(suffix)
                return result
            return altered
        # A host that disagrees by crashing must still report the comparison
        # exit 3, not the runtime-error exit 4.
        for suffix in (b"printf 'wrong\\n'\n", b"printf 'wrong\\n'\nexit 9\n"):
            try:
                driver.emit = appending_emit(suffix)
                with contextlib.redirect_stderr(io.StringIO()) as diagnostic:
                    status = driver.execute(SimpleNamespace(entry='main', fuel=1000000, host='bash'),
                                            ROOT / 'examples', 'M0Spine.tet')
                require(status == 3 and 'disagreement' in diagnostic.getvalue(),
                        f'Disagreement exit for {suffix!r}: {status}')
            finally:
                driver.emit = original_emit
        require(run(['./tether', 'run', 'examples/M0Spine.tet']) == b'1\n', 'Run output')
        require(run(['./tether', 'axioms', 'examples/M0Spine.tet']) == b'', 'Axiom disclosure')
        run(['./tether', 'check', 'examples/M0Spine.tet', '--passes'], diagnostic=b'PASSES def=main walks=3')
        run(['./tether', 'check', 'examples/M0Spine.tet', '--fuel', '0'], code=1, diagnostic=b'budget')
        for entry in ('higherMain', 'constructed', 'inlineMain', 'branched', 'partialMain'):
            destination = work / ('bad-' + entry)
            run(['./tether', 'emit', 'examples/ShCases.tet', '--entry', entry, '-o', str(destination)],
                code=2, diagnostic=b'SH-FIRST-ORDER')
            require(not destination.exists(), 'Failed emit published output')
        run(['./tether', 'emit', 'examples/M0Spine.tet', '-o', str(work / 'main')], code=2)
        bad = work / 'Bad.tet'
        bad.write_text('module Wrong\n')
        run(['./tether', 'check', str(bad)], code=1)
        run(['./tether', 'emit', str(bad), '-o', str(work / 'bad')], code=2)
        print('PASS DRIVER check=1 emit=1 run=1 exec=3 axioms=1 passes=1 refusals=5 disagreements=2',
              flush=True)
        shell = work / 'main/prog.sh'
        original = shell.read_bytes()
        require(original.count(b'local function bytes(s)') == 1, 'Mutation anchor')
        try:
            shell.write_bytes(original.replace(b'local function bytes(s)', b'local function bytes(t)', 1))
            run(['node', 'dev/lua-same.mjs', str(work / 'main')], code=1, diagnostic=b'FAIL LUA-SAME')
            print('KILLED ARTIFACT-BYTE by LUA-SAME', flush=True)
        finally:
            shell.write_bytes(original)
        run(['node', 'dev/lua-same.mjs', str(work / 'main')])
        # The invocation key literals sit outside the carried body block, so
        # this mutant is invisible to a body-bytes comparison alone.
        start = original.index(b"\ninvoke '")
        literal = original.index(b"$'\\", start)
        digits = int(original[literal + 3:literal + 6], 8)
        require(0 < digits < 128, 'Key literal anchor')
        try:
            shell.write_bytes(original[:literal + 3] + f'{digits ^ 1:03o}'.encode() +
                              original[literal + 6:])
            run(['node', 'dev/lua-same.mjs', str(work / 'main')], code=1, diagnostic=b'FAIL LUA-SAME')
            print('KILLED ARTIFACT-KEY by LUA-SAME', flush=True)
        finally:
            shell.write_bytes(original)
        run(['node', 'dev/lua-same.mjs', str(work / 'main')])
        overloaded = work / 'Overloaded.tet'
        source = (ROOT / 'examples/M0Spine.tet').read_text().replace('module M0Spine', 'module Overloaded')
        # The ruled bound is 150 ms and never moves. The added work rises until
        # the real timer crosses it on the machine running this ladder.
        added, crossed, median = 2000, 0, 0.0
        while not crossed and added <= 16000:
            overloaded.write_text(source + ''.join(f'\ndef ballast{i} : Nat := {i}\n' for i in range(added)))
            with contextlib.redirect_stdout(io.StringIO()):
                samples = bench.measure(work, overloaded.name, work / f'overloaded-{added}')
                survived = bench.report(samples)
            if survived:
                added *= 2
            else:
                crossed, median = added, statistics.median(samples)
        require(crossed, f'Overloaded compile survived M0-TIME at {added // 2} definitions')
        print(f'MUTANT-BENCH m0-time median_ms={median:.3f} min_ms={min(samples):.3f} '
              f'max_ms={max(samples):.3f} runs=5', flush=True)
        print(f'MUTANT-M0-TIME exceeded median_ms={median:.3f} bound_ms=150', flush=True)
        print(f'KILLED SPINE-WORK by M0-TIME definitions_added={crossed}', flush=True)
        with contextlib.redirect_stdout(io.StringIO()):
            require(bench.report([149.0] * 5), 'Timing positive control')
            require(not bench.report([150.0] * 5), 'Timing boundary control')
        print('PASS M0-TIME-BOUNDARY below=149 at=150', flush=True)
        print('PASS STAGE-F-MUTATIONS killed=3 survived=0 restored=2', flush=True)
        print('PASS STAGE-F-TESTS', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL STAGE-F-TESTS {error}', file=sys.stderr)
        sys.exit(1)
