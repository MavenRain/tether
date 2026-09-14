#!/usr/bin/env python3
"""Tether command host. Source resolution and compilation are checked in OCaml."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / '_build/default/bin/tether.exe'


def report_bytes(data):
    # A caller may redirect sys.stderr to a text stream with no binary buffer,
    # so fall back to a decoded write instead of raising AttributeError.
    binary = getattr(sys.stderr, 'buffer', None)
    return (binary.write(data) if binary is not None
            else sys.stderr.write(data.decode('utf-8', 'replace')))


def compile_rows(mode, source_root, path, entry='main', fuel=1000000):
    if not BINARY.is_file():
        raise ValueError('Build the compiler first: dune build bin/tether.exe')
    rows, started = [], None
    source_root = source_root.resolve()
    with subprocess.Popen([str(BINARY), mode, path, entry, str(fuel)], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE) as process:
        try:
            for line in process.stdout:
                if started is None:
                    started = time.perf_counter_ns()
                if not line.startswith(b'READ '):
                    rows.append(line.rstrip(b'\n'))
                    continue
                request = line[5:].rstrip(b'\n').decode('utf-8')
                if request in ('@reactor', '@redis'):
                    target = ROOT / 'runtime' / (request[1:] + '.kan')
                else:
                    target = (source_root / request).resolve()
                    if not target.is_relative_to(source_root):
                        raise ValueError('HOST-ESCAPE source leaves the selected root')
                data = target.read_bytes()
                if len(data) > 1048576:
                    raise ValueError('HOST-OVERSIZE source exceeds 1 MiB')
                process.stdin.write(str(len(data)).encode() + b'\n' + data)
                process.stdin.flush()
            code = process.wait()
        except BaseException:
            process.kill()
            process.wait()
            raise
    return code, rows, started


def write_artifacts(rows, output):
    files, scripts, plan = {}, [], None
    for row in rows:
        fields = row.split(b' ')
        if fields[0] in (b'SH', b'WASM') and len(fields) == 2:
            name = 'prog.sh' if fields[0] == b'SH' else 'prog.wasm'
            if name in files:
                raise ValueError('Duplicate compiler artifact')
            files[name] = bytes.fromhex(fields[1].decode())
        elif fields[0] == b'CLIENT' and len(fields) >= 2 and plan is None:
            plan = {'version': 1, 'answer': int(fields[1]),
                    'invokes': [name.decode('ascii') for name in fields[2:]]}
        elif fields[0] == b'SCRIPT' and len(fields) >= 4:
            _, name, sha, body, *keys = fields
            body = bytes.fromhex(body.decode())
            if hashlib.sha1(body).hexdigest() != sha.decode():
                raise ValueError('Compiler body hash mismatch')
            stem = f'body-{len(scripts)}'
            files[stem + '.lua'] = body
            scripts.append({'entry': name.decode('ascii'), 'sha1': sha.decode('ascii'),
                            'stem': stem, 'keys': [bytes.fromhex(k.decode()).decode('ascii') for k in keys]})
        else:
            raise ValueError('Invalid compiler response')
    names = [s['entry'] for s in scripts]
    if not {'prog.sh', 'prog.wasm'} <= files.keys() or plan is None or len(set(names)) != len(names):
        raise ValueError('Missing or duplicate compiler artifacts')
    if set(plan['invokes']) != set(names) or not -1 <= plan['answer'] < len(plan['invokes']):
        raise ValueError('Invalid Client schedule')
    files['scripts.json'] = (json.dumps(scripts, indent=2) + '\n').encode()
    files['client.json'] = (json.dumps(plan, indent=2) + '\n').encode()
    output.mkdir(parents=True, exist_ok=False)
    try:
        for name, data in files.items():
            (output / name).write_bytes(data)
        (output / 'prog.sh').chmod(0o755)
    except BaseException:
        shutil.rmtree(output)
        raise


def emit(source_root, path, output, entry='main', fuel=1000000):
    code, rows, started = compile_rows('emit', source_root, path, entry, fuel)
    if code:
        return code, None
    write_artifacts(rows, output)
    return 0, (time.perf_counter_ns() - started) / 1000000


def reply_text(row):
    text = row.decode('ascii')
    def parse(value):
        if value == 'null':
            return None
        if value.startswith('array:[') and value.endswith(']'):
            parts, start, depth = [], 7, 0
            for index in range(7, len(value) - 1):
                if value[index] == '[':
                    depth += 1
                elif value[index] == ']':
                    depth -= 1
                elif value[index] == ',' and depth == 0:
                    parts.append(parse(value[start:index]))
                    start = index + 1
            if value[start:-1]:
                parts.append(parse(value[start:-1]))
            return parts
        kind, sep, payload = value.partition(':')
        if not sep or kind not in ('int', 'bulk', 'status', 'error'):
            raise ValueError('Invalid store reply')
        data = bytes.fromhex(payload).decode('utf-8')
        if kind == 'error':
            raise ValueError(data)
        return data
    value = parse(text)
    # jq escapes the DEL byte and JSON.stringify does not, so the one canonical
    # array text escapes it here too. Every host must print the same bytes.
    return ((json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('\x7f', '\\u007f')
             if isinstance(value, list) else '' if value is None else value) + '\n').encode()


def lua_config(output, target):
    def literal(text):
        return '"' + ''.join(f'\\{byte:03d}' for byte in str(text).encode()) + '"'
    scripts = {s['entry']: s for s in json.loads((output / 'scripts.json').read_text())}
    plan = json.loads((output / 'client.json').read_text())
    calls = []
    for name in plan['invokes']:
        script = scripts[name]
        calls.append('{path=' + literal(output / (script['stem'] + '.lua')) + ',keys={' +
                     ','.join(literal(key) for key in script['keys']) + '}}')
    target.write_text('return {values={},reply=true,invokes={' + ','.join(calls) +
                      '},answer=' + str(plan['answer']) + '}\n')


def execute(args, source_root, path):
    # The store leg and each selected host must start with the same empty store.
    # The Redis hosts use an owned temporary loopback server and never a user's DB.
    with tempfile.TemporaryDirectory(prefix='tether-exec-') as directory:
        work = Path(directory)
        output = work / 'program'
        code, _ms = emit(source_root, path, output, args.entry, args.fuel)
        if code:
            return code
        code, rows, _start = compile_rows('run', source_root, path, args.entry, args.fuel)
        if code:
            return code
        expected = reply_text(rows[0].removeprefix(b'REPLY '))
        if args.host == 'luajit':
            config = work / 'lua-config.lua'
            lua_config(output, config)
            child = subprocess.run(['luajit', '-joff', str(ROOT / 'dev/lua-store.lua'), str(config)],
                                   capture_output=True, timeout=30)
        else:
            # Import the local process owner only when a Redis host is requested.
            spec = importlib.util.spec_from_file_location('tether_local', ROOT / 'bin/local.py')
            local = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(local)
            with local.hosts(work) as (port, env):
                command = (['node', str(ROOT / 'runtime/redis-host.mjs'), str(output / 'prog.wasm'), str(port)]
                           if args.host == 'node' else ['/bin/bash', str(output / 'prog.sh')])
                child = subprocess.run(command, capture_output=True, env=env, timeout=30)
        # A host that disagrees by crashing is a disagreement first: compare the
        # output before the exit status, so exit 4 means the outputs agreed.
        observed = child.stdout
        if args.host == 'luajit' and child.returncode == 0:
            try:
                observed = reply_text(child.stdout.removesuffix(b'\n'))
            except ValueError:
                # An undecodable twin reply is a disagreement, never an
                # agreement that crashed: report the raw bytes and exit 3.
                report_bytes(child.stderr)
                report_bytes(child.stdout)
                print('TETHER E2E disagreement', file=sys.stderr)
                return 3
        if observed != expected:
            report_bytes(child.stderr)
            print('TETHER E2E disagreement', file=sys.stderr)
            return 3
        if child.returncode:
            report_bytes(child.stderr)
            return 4
        sys.stdout.buffer.write(observed)
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('check', 'emit', 'run', 'exec', 'axioms'):
        p = commands.add_parser(command)
        p.add_argument('file', type=Path)
        p.add_argument('--root', type=Path, help='source root, defaults to the file directory')
        p.add_argument('--entry', default='main')
        p.add_argument('--fuel', type=int, default=1000000)
        if command == 'emit':
            p.add_argument('-o', '--output', type=Path, required=True)
        if command == 'check':
            p.add_argument('--passes', action='store_true')
        if command == 'exec':
            p.add_argument('--host', choices=('node', 'bash', 'luajit'), required=True)
    commands.add_parser('spec-count')
    commands.add_parser('bench')
    args = parser.parse_args()
    error_code = 2 if args.command == 'emit' else 4 if args.command in ('run', 'exec') else 1
    try:
        if args.command in ('spec-count', 'bench'):
            script = 'r0-count.sh' if args.command == 'spec-count' else 'm0-bench.sh'
            return subprocess.run(['sh', str(ROOT / 'dev' / script)], cwd=ROOT).returncode
        source_root = (args.root or args.file.parent).resolve()
        path = str(args.file.resolve().relative_to(source_root))
        if args.command == 'emit':
            code, _ms = emit(source_root, path, args.output, args.entry, args.fuel)
            if code == 0:
                print(f'PASS EMIT {args.output / "prog.wasm"} {args.output / "prog.sh"}')
            return code
        if args.command == 'exec':
            return execute(args, source_root, path)
        mode = 'passes' if args.command == 'check' and args.passes else args.command
        code, rows, _start = compile_rows(mode, source_root, path, args.entry, args.fuel)
        if code:
            return code
        if mode == 'run':
            if len(rows) != 1 or not rows[0].startswith(b'REPLY '):
                raise ValueError('Invalid store response')
            sys.stdout.buffer.write(reply_text(rows[0][6:]))
        else:
            for row in rows:
                sys.stdout.buffer.write(row + b'\n')
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired, RecursionError) as error:
        print(f'TETHER {error}', file=sys.stderr)
        return error_code


if __name__ == '__main__':
    sys.exit(main())
