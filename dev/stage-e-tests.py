#!/usr/bin/env python3
"""Owned localhost integration, independent store checks and Stage E mutations."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
KEY = '{counter}:hits:visits'
# Child deadlines. The emitter and the Wasm build are minutes of work under a
# loaded machine, so they carry their own larger deadline. Both are overridable.
TIMEOUT = int(os.environ.get('TETHER_CHILD_TIMEOUT', '120'))
BUILD_TIMEOUT = int(os.environ.get('TETHER_BUILD_TIMEOUT', '600'))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


checker = module('tether_check', ROOT / 'dev/check.py')
split = module('decoder_split', ROOT / 'dev/decoders-split.py')


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def run(args, *, code=0, env=None, data=None, timeout=None):
    deadline = TIMEOUT if timeout is None else timeout
    try:
        result = subprocess.run(args, cwd=ROOT, env=env, input=data, capture_output=True, timeout=deadline)
    except subprocess.TimeoutExpired:
        print(f'FAIL STAGE-E-TESTS timeout {deadline}s {args}', flush=True)
        raise SystemExit(1)
    require(result.returncode == code, f'{args}: exit={result.returncode}\n{result.stdout!r}\n{result.stderr!r}')
    return result.stdout


def lua_string(text):
    return '"' + ''.join(f'\\{byte:03d}' for byte in text.encode()) + '"'


def lua_run(directory, output, initial):
    scripts = {item['entry']: item for item in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = []
    for name in plan['invokes']:
        script = scripts[name]
        keys = ','.join(lua_string(key) for key in script['keys'])
        calls.append('{path=' + lua_string(str(output / (script['stem'] + '.lua'))) + ',keys={' + keys + '}}')
    values = '' if initial is None else '[' + lua_string(KEY) + ']=' + lua_string(initial)
    config = directory / 'lua-config.lua'
    config.write_text('return {values={' + values + '},invokes={' + ','.join(calls) +
                      '},answer=' + str(plan['answer']) + '}\n')
    return run(['luajit', '-joff', 'dev/lua-store.lua', str(config)])


def store_run(source, entry, initial):
    rows = []
    code = checker.check(ROOT / 'examples', source, command=[str(ROOT / '_build/default/dev/store_run.exe'),
                          source, entry, KEY, '@missing' if initial is None else initial, '1000000'], receive=rows.append)
    require(code == 0 and len(rows) == 1, f'STORE run exit={code} rows={rows}')
    row = rows[0].removeprefix(b'REPLY ').rstrip(b'\n')
    if row == b'null':
        return 'null', b'\n'
    kind, _colon, payload = row.partition(b':')
    require(kind in (b'int', b'bulk', b'status'), f'STORE reply {row}')
    return kind.decode(), bytes.fromhex(payload.decode()) + b'\n'


def store_fault(source, entry, initial):
    """Run the interpreter on a failing case and capture the diagnostic text."""
    with tempfile.TemporaryFile() as sink:
        saved = os.dup(2)
        os.dup2(sink.fileno(), 2)
        try:
            code = checker.check(ROOT / 'examples', source, receive=lambda _row: None,
                                 command=[str(ROOT / '_build/default/dev/store_run.exe'), source, entry, KEY,
                                          '@missing' if initial is None else initial, '1000000'])
        finally:
            os.dup2(saved, 2)
            os.close(saved)
        sink.seek(0)
        return code, sink.read()


def reactor_fixture(directory, output, invalid=False):
    script = json.loads((output / 'scripts.json').read_text())[0]
    body = (output / (script['stem'] + '.lua')).read_bytes()
    digest = ('0' * 40 if invalid else script['sha1']).encode()
    source = directory / ('invalid.kan' if invalid else 'probe.kan')
    constants = [('probeBody', body), ('probeSha', digest), ('probeKey', KEY.encode())]
    source.write_text(''.join('def ' + name + ' : Bytes := b"' + ''.join(f'\\x{b:02x}' for b in data) + '"\n'
                              for name, data in constants) + (ROOT / 'dev/redis-reactor.kan').read_text())
    wasm = source.with_suffix('.wasm')
    exports = ['emptyBytes', 'consBytes', 'bytesEmpty', 'bytesHead', 'bytesTail',
               'emptyWords', 'wordsEmpty', 'wordsHead', 'wordsTail', 'init', 'resume',
               'requestCode', 'requestArgs', 'requestBody', 'exitCode']
    command = [str(ROOT / '_build/default/vendor/kanon/bin/kanon.exe'), 'build',
               'runtime/reactor.kan', str(source), '-o', str(wasm)]
    for name in exports:
        command.extend(['--export', name])
    run(command, timeout=BUILD_TIMEOUT)
    return wasm


def source_mutations(directory):
    require(split.check(ROOT), 'DECODERS-SPLIT control')
    root = directory / 'integrity'
    for name in ('dev', 'print', 'store', 'runtime', 'vendor/kanon/lib', 'vendor/kanon/wasm'):
        shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns('__pycache__'))
    gate = [sys.executable, '-P', str(root / 'dev/trusted-lines.py')]
    run(gate)
    killed = 0
    rest = root / 'runtime/rest-decode.mjs'
    original = rest.read_bytes()
    rest.write_text("export { decode } from './redis-host.mjs';\n")
    require(not split.check(root), 'DECODERS-SPLIT merged decoder survived')
    rest.write_bytes(original)
    require(split.check(root), 'DECODERS-SPLIT restore')
    print('KILLED MERGED-DECODER by DECODERS-SPLIT', flush=True)
    killed += 1
    # The harder merge: the Node decode body copied into the REST file, with no
    # import, no re-export and the local fault class kept.
    node_source = (root / 'runtime/redis-host.mjs').read_text()
    start = node_source.index('export function decode(')
    stop = node_source.index('export ', start + len('export '))
    text = original.decode()
    copied = (text[:text.index('export function decode(')] +
              node_source[start:stop].replace('RedisFault', 'RestFault') +
              text[text.index('export function envelope('):])
    rest.write_text(copied)
    require(not split.check(root), 'DECODERS-SPLIT copied decoder survived')
    rest.write_bytes(original)
    require(split.check(root), 'DECODERS-SPLIT restore')
    print('KILLED COPIED-DECODER by DECODERS-SPLIT', flush=True)
    killed += 1
    for name in ('store/store.ml', 'store/interp.ml', 'runtime/redis-host.mjs',
                 'runtime/rest-twin.mjs', 'runtime/rest-decode.mjs'):
        path = root / name
        original = path.read_bytes()
        path.unlink()
        require(b'TRUSTED-LINES FAIL' in run(gate, code=1), 'missing implementation survived')
        path.write_bytes(original)
        run(gate)
        killed += 1
    for name, bound in [('store/store.ml', 200), ('runtime/redis-host.mjs', 300), ('runtime/rest-twin.mjs', 300)]:
        path = root / name
        original = path.read_bytes()
        path.write_bytes(original + b'\n' * (bound + 1))
        require(b' FAIL' in run(gate, code=1), 'bound mutant survived')
        path.write_bytes(original)
        run(gate)
        killed += 1
    for folder, extension in [('store', 'ml'), ('store', 'mli'), ('runtime', 'mjs'), ('runtime', 'js')]:
        extra = root / folder / ('uncounted.' + extension)
        extra.write_text('\n')
        require(b'uncounted implementation files' in run(gate, code=1), 'uncounted implementation survived')
        extra.unlink()
        run(gate)
        killed += 1
    print(f'PASS STAGE-E-INTEGRITY killed={killed} restored=1', flush=True)
    return killed


def main():
    require(split.check(ROOT), 'DECODERS-SPLIT')
    print('DECODERS-SPLIT files=2', flush=True)
    with tempfile.TemporaryDirectory(prefix='tether-e-') as temporary:
        directory = Path(temporary)
        outputs = {}
        entries = [('M0Spine.tet', 'main'), ('ShCases.tet', 'twice'), ('ShCases.tet', 'capturedReply'),
                   ('ShCases.tet', 'exactMain'), ('HostCases.tet', 'readMain'), ('HostCases.tet', 'incrementMain')]
        for source, entry in entries:
            output = directory / entry
            run([sys.executable, '-P', 'dev/emit-sh.py', '--root', 'examples', source, '--entry', entry,
                 '-o', str(output)], timeout=BUILD_TIMEOUT)
            outputs[entry] = (source, output)
        reactor = reactor_fixture(directory, outputs['main'][1])
        invalid_reactor = reactor_fixture(directory, outputs['main'][1], invalid=True)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        rest_log = directory / 'rest-requests.jsonl'
        env = dict(os.environ, TETHER_REDIS_PORT=str(port), TETHER_TOKEN='tether-local-fixture',
                   TETHER_REST_LOG=str(rest_log), TETHER_REST_PORT='0')
        processes = []
        with (directory / 'redis.log').open('wb') as log, (directory / 'rest.log').open('wb') as rest_error:
            try:
                redis = subprocess.Popen(['redis-server', '--bind', '127.0.0.1', '--port', str(port),
                                          '--save', '', '--appendonly', 'no', '--daemonize', 'no'], stdout=log, stderr=log)
                processes.append(redis)
                (directory / 'redis.pid').write_text(str(redis.pid) + '\n')
                cli = ['redis-cli', '-h', '127.0.0.1', '-p', str(port)]
                for _attempt in range(100):
                    require(redis.poll() is None, 'Redis exited before readiness')
                    ping = subprocess.run(cli + ['PING'], capture_output=True, timeout=2)
                    if ping.returncode == 0 and ping.stdout == b'PONG\n':
                        break
                    time.sleep(0.05)
                else:
                    raise AssertionError('Redis readiness timeout')
                twin = subprocess.Popen(['node', 'runtime/rest-twin.mjs'], cwd=ROOT, env=env,
                                        stdout=subprocess.PIPE, stderr=rest_error)
                processes.append(twin)
                require(select.select([twin.stdout], [], [], 10)[0], 'REST readiness timeout')
                line = twin.stdout.readline().decode().strip()
                require(line.startswith('REST-UP port='), f'REST readiness {line}')
                env['TETHER_URL'] = 'http://127.0.0.1:' + line.split('=')[1] + '/'

                def reset(initial):
                    run(cli + ['FLUSHDB'])
                    run(cli + ['SCRIPT', 'FLUSH'])
                    if initial is not None:
                        run(cli + ['SET', KEY, initial])

                def bash(output, initial):
                    reset(initial)
                    return run(['/bin/bash', str(output / 'prog.sh')], env=env)

                # The fourth column pins the Reply constructor the interpreter must
                # return, so a permuted constructor is a mismatch and not a tie.
                cases = [('main', '9007199254740992', '9007199254740993', 'bulk'),
                         ('main', None, '1', 'bulk'), ('main', '-10', '-9', 'bulk'),
                         ('twice', '9007199254740992', '9007199254740994', 'bulk'),
                         ('capturedReply', '0', '1', 'bulk'), ('exactMain', None, '9007199254740993', 'int'),
                         ('incrementMain', '9223372036854775806', '9223372036854775807', 'int'),
                         ('incrementMain', '-9223372036854775808', '-9223372036854775807', 'int'),
                         ('readMain', None, '', 'null'), ('readMain', 'a\nlast\n', 'a\nlast\n', 'bulk')]
                for entry, initial, expected, tag in cases:
                    source, output = outputs[entry]
                    wanted = expected.encode() + b'\n'
                    lua = lua_run(directory, output, initial)
                    reset(initial)
                    node = run(['node', 'dev/run-node.mjs', str(output)], env=env)
                    sh = bash(output, initial)
                    kind, stored = store_run(source, entry, initial)
                    require(lua == node == sh == stored == wanted and kind == tag,
                            f'E2E-3WAY {entry} lua={lua!r} node={node!r} sh={sh!r} '
                            f'store={kind}:{stored!r} expected={tag}:{wanted!r}')
                    print(f'E2E-3WAY luajit=1 node=1 sh=1 store=1 entry={entry} '
                          f'reply={json.dumps(expected)} constructor={tag}', flush=True)
                # Count the genuine REST requests, including the first-use load.
                start = len(rest_log.read_text().splitlines())
                require(bash(outputs['twice'][1], '0') == b'2\n', 'LOAD-ONCE stdout')
                calls = [json.loads(row) for row in rest_log.read_text().splitlines()[start:]]
                plan = json.loads((outputs['twice'][1] / 'client.json').read_text())
                require([row['command'] for row in calls] == ['SCRIPT', 'EVALSHA', 'EVALSHA'] and
                        calls[0]['subcommand'] == 'LOAD', f'LOAD-ONCE {calls}')
                require(len(calls[2:]) == len(plan['invokes'][1:]) == 1, 'LOAD-ONCE steady state')
                require(env['TETHER_TOKEN'] not in rest_log.read_text(), 'REST token log')
                print('LOAD-ONCE rest_calls=1 invoke_lines=1 warmup_calls=2 total_calls=3', flush=True)
                # Keep one Node client alive across a real SCRIPT FLUSH.
                reset('9007199254740992')
                print(run(['node', 'dev/host-live.mjs', str(outputs['main'][1]), str(port)]).decode().rstrip(), flush=True)
                print(run(['node', 'dev/reactor-live.mjs', str(reactor), str(invalid_reactor), str(port)]).decode().rstrip(), flush=True)
                # Both hosts refuse a real overflow rather than rounding it.
                faults = [('incrementMain', '9223372036854775807',
                           b'ERR increment or decrement would overflow'),
                          ('incrementMain', 'not-an-integer',
                           b'ERR value is not an integer or out of range')]
                for entry, initial, message in faults:
                    for args in [['node', 'dev/run-node.mjs', str(outputs[entry][1])],
                                 ['/bin/bash', str(outputs[entry][1] / 'prog.sh')]]:
                        reset(initial)
                        try:
                            result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=TIMEOUT)
                        except subprocess.TimeoutExpired:
                            print(f'FAIL STAGE-E-TESTS timeout {TIMEOUT}s {args}', flush=True)
                            raise SystemExit(1)
                        require(result.returncode == 4 and not result.stdout and message in result.stderr,
                                f'HOST fault {result}')
                    # The interpreter must refuse the same case with the same text.
                    code, diagnostic = store_fault(outputs[entry][0], entry, initial)
                    require(code == 4 and message in diagnostic,
                            f'STORE fault exit={code} stderr={diagnostic!r} expected={message!r}')
                print(f'PASS HOST-FAULTS cases={len(faults) * 3}', flush=True)
                # Change the Bash body and its expected hash, so only semantic comparison kills it.
                output = outputs['main'][1]
                shell = output / 'prog.sh'
                original = shell.read_bytes()
                script = json.loads((output / 'scripts.json').read_text())[0]
                body = (output / (script['stem'] + '.lua')).read_bytes()
                require(body.count(b"'INCR'") == 1, 'DECR mutation anchor')
                changed = body.replace(b"'INCR'", b"'DECR'")
                digest = hashlib.sha1(changed).hexdigest().encode()
                shell.write_bytes(original.replace(body, changed).replace(script['sha1'].encode(), digest))
                try:
                    # Rerun the comparison of the case loop: only the Bash body is
                    # mutated, so the four legs must now disagree.
                    wanted = b'9007199254740993\n'
                    actual = bash(output, '9007199254740992')
                    lua = lua_run(directory, output, '9007199254740992')
                    reset('9007199254740992')
                    node = run(['node', 'dev/run-node.mjs', str(output)], env=env)
                    kind, stored = store_run(outputs['main'][0], 'main', '9007199254740992')
                    require(lua == node == stored == wanted and kind == 'bulk',
                            f'DECR reference legs lua={lua!r} node={node!r} store={kind}:{stored!r}')
                    require(not (lua == node == actual == stored == wanted),
                            f'E2E-3WAY mutation survived sh={actual!r}')
                finally:
                    shell.write_bytes(original)
                require(bash(output, '9007199254740992') == b'9007199254740993\n', 'E2E restore')
                print('KILLED DECR-SPINE by E2E-3WAY reply comparison', flush=True)
            finally:
                for process in reversed(processes):
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                    if process.stdout:
                        process.stdout.close()
                require(all(process.poll() is not None for process in processes), 'HOST cleanup')
                print(f'HOSTS-STOPPED owned={len(processes)}', flush=True)
        killed = source_mutations(directory) + 1
        require(killed == 15, 'Stage E mutant census')
        print(f'PASS STAGE-E-MUTATIONS killed={killed} restored=1', flush=True)
    print('PASS STAGE-E-TESTS cases=10', flush=True)


if __name__ == '__main__':
    main()
