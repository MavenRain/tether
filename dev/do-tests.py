#!/usr/bin/env python3
"""Check do syntax through real modules, artifacts and independent hosts."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TAG = '(tag b"counter")'
KEY = '{counter}:hits:visits'
HEADER = 'module Case\nschema hits : String -> Key (Str Int64) tag b"counter"\n'


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


local = module('do_local', 'bin/local.py')
previous = module('do_previous', 'dev/stage-e-tests.py')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run(args, code=0, diagnostic=None, env=None):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, env=env, timeout=120)
    require(result.returncode == code,
            f'{args}: exit={result.returncode}\n{result.stdout!r}\n{result.stderr!r}')
    if diagnostic is not None:
        require(diagnostic in result.stdout + result.stderr, f'Missing {diagnostic!r}: {args}')
    return result.stdout


def programs():
    # Each reference is written in the pre-existing continuation syntax.
    pairs = [
        ('counter', f'Script Reply {TAG}',
         f'do {{ a <- incr Reply {TAG} (hits b"visits"); '
         f'b <- get Reply Int64 {TAG} (hits b"visits"); pure Reply {TAG} b }}',
         f'incr Reply {TAG} (hits b"visits") (fun (a : Reply) => '
         f'get Reply Int64 {TAG} (hits b"visits") (fun (b : Reply) => pure Reply {TAG} b))'),
        ('saved', f'Script Reply {TAG}',
         f'do {{ a <- incr Reply {TAG} (hits b"visits"); '
         f'_ <- incr Reply {TAG} (hits b"visits"); pure Reply {TAG} a }}',
         f'incr Reply {TAG} (hits b"visits") (fun (a : Reply) => '
         f'incr Reply {TAG} (hits b"visits") (fun (_ : Reply) => pure Reply {TAG} a))'),
        ('literal', f'Script Reply {TAG}',
         f'do {{ -- do {{ fake <- ; }}\n pure Reply {TAG} (bulk b"do {{ r <- ; }}\\n\\0"); }}',
         f'pure Reply {TAG} (bulk b"do {{ r <- ; }}\\n\\0")'),
        ('main', 'Client Reply',
         f'do {{ r <- inv Reply {TAG} counter; done Reply r }}',
         f'inv Reply {TAG} counter (fun (r : Reply) => done Reply r)'),
        ('earlier', 'Client Reply',
         f'do {{ a <- inv Reply {TAG} counter; b <- inv Reply {TAG} counter; done Reply a }}',
         f'inv Reply {TAG} counter (fun (a : Reply) => '
         f'inv Reply {TAG} counter (fun (b : Reply) => done Reply a))'),
        ('shadow', 'Client Reply',
         f'do {{ r <- inv Reply {TAG} counter; r <- inv Reply {TAG} counter; done Reply r }}',
         f'inv Reply {TAG} counter (fun (r : Reply) => '
         f'inv Reply {TAG} counter (fun (r : Reply) => done Reply r))'),
        ('nested', 'Client Reply',
         f'do {{ r <- inv Reply {TAG} saved; do {{ done Reply r; }} }}',
         f'inv Reply {TAG} saved (fun (r : Reply) => done Reply r)'),
        ('bytes', 'Client Reply',
         f'do {{ r <- inv Reply {TAG} literal; done Reply r }}',
         f'inv Reply {TAG} literal (fun (r : Reply) => done Reply r)'),
        ('stopped', 'Client Reply',
         f'do {{ _ <- inv Reply {TAG} counter; fail Reply Network }}',
         f'inv Reply {TAG} counter (fun (_ : Reply) => fail Reply Network)'),
        ('noCalls', 'Client Reply', 'do { fail Reply Network; }', 'fail Reply Network'),
    ]
    return tuple(HEADER + '\n'.join(f'def {name} : {ty} := {pair[column]}\n'
                 for name, ty, *pair in pairs) for column in (0, 1))


def refusals(work):
    action = f'inv Reply {TAG} (pure Reply {TAG} nil)'
    cases = [
        ('missing-final', f'do {{ r <- {action}; }}', b'DO-SYNTAX'),
        ('missing-close', f'do {{ r <- {action}; done Reply r', b'DO-SYNTAX'),
        ('wrong-type', f'do {{ r <- inv Nat {TAG} (pure Reply {TAG} nil); done Reply r }}', b'CHECK mismatch'),
        ('wrong-slot', f'do {{ r <- inv Reply (tag b"other") (pure Reply {TAG} nil); done Reply r }}', b'CHECK mismatch'),
        ('self-scope', f'do {{ r <- inv Reply {TAG} (pure Reply {TAG} r); done Reply r }}', b'unbound: r'),
        ('escape-scope', f'do {{ r <- {action}; done Reply r }}\ndef escaped : Reply := r', b'unbound: r'),
        ('protected-binder', f'do {{ tag <- {action}; done Reply tag }}', b'RESERVED binder tag'),
        ('bad-command', 'do { r <- done Reply nil; done Reply r }',
         b'CHECK mismatch: the head of an application is not a function'),
    ]
    source = work / 'Bad.tet'
    clean = 0
    for name, term, diagnostic in cases:
        source.write_text('module Bad\ndef main : Client Reply := ' + term + '\n')
        run(['./tether', 'check', str(source)], code=1, diagnostic=diagnostic)
        target = work / name
        run(['./tether', 'emit', str(source), '-o', str(target)], code=2, diagnostic=diagnostic)
        require(not target.exists(), f'Failed check published artifacts: {name}')
        clean += 1
    # An inline Script still checks but the first-order printer refuses it.
    inline = [('inline', f'do {{ r <- {action}; done Reply r }}', b'SH-FIRST-ORDER')]
    for name, term, diagnostic in inline:
        source.write_text('module Bad\ndef main : Client Reply := ' + term)
        run(['./tether', 'check', str(source)])
        target = work / name
        run(['./tether', 'emit', str(source), '-o', str(target)], code=2, diagnostic=diagnostic)
        require(not target.exists(), f'Inline refusal published artifacts: {name}')
        clean += 1
    # Every counter below is the number of checks this run actually made.
    require(clean == len(cases) + len(inline), 'Output cleanup count')
    print(f'PASS DO-CHECK refusals={len(cases)} first_order={len(inline)} '
          f'atomic_output={clean}', flush=True)


def example():
    """Drive the documented example with the documented commands."""
    path = 'examples/DoCounter.tet'
    run(['./tether', 'check', path])
    entries = [('main', b'1\n', 0, None), ('earlier', b'1\n', 0, None),
               ('stopped', b'', 4, b'STORE-CLIENT-FAULT')]
    for entry, expected, code, diagnostic in entries:
        require(run(['./tether', 'run', path, '--entry', entry], code=code,
                    diagnostic=diagnostic) == expected, 'Example entry ' + entry)
    return 1 + len(entries)


def main():
    with tempfile.TemporaryDirectory(prefix='tether-do-') as temporary:
        work = Path(temporary)
        paths = []
        for name, source in zip(('sugar', 'explicit'), programs(), strict=True):
            folder = work / name
            folder.mkdir()
            path = folder / 'Case.tet'
            path.write_text(source)
            paths.append(path)
            run(['./tether', 'check', str(path), '--passes'], diagnostic=b'PASSES def=main walks=3')
            require(run(['./tether', 'axioms', str(path)]) == b'', 'Added an axiom')
        # Imported modules must use the same syntax expansion and schema rules.
        imported = work / 'Imported.tet'
        imported.write_text('module Imported\nimport Case\ndef imported : Client Reply := '
                            f'do {{ r <- inv Reply {TAG} counter; done Reply r }}')
        (work / 'Case.tet').write_text(programs()[0])
        require(run(['./tether', 'run', str(imported), '--entry', 'imported']) == b'1\n', 'Imported do')
        imports = 1
        kinds = {'wasm': '.wasm', 'bash': '.sh', 'lua': '.lua', 'metadata': '.json'}
        counted = dict.fromkeys(kinds, 0)
        cases = [('main', b'1\n', b'1\n', 0), ('earlier', b'1\n', b'2\n', 0),
                 ('shadow', b'2\n', b'2\n', 0), ('nested', b'1\n', b'2\n', 0),
                 ('bytes', b'do { r <- ; }\n\0\n', b'\n', 0),
                 ('stopped', b'', b'1\n', 4), ('noCalls', b'', b'\n', 4)]
        for entry, expected, _stored, code in cases:
            for path in paths:
                run(['./tether', 'emit', str(path), '--entry', entry, '-o', str(path.parent / entry)])
                require(run(['./tether', 'run', str(path), '--entry', entry], code=code) == expected,
                        'Interpreter ' + entry)
            left, right = (path.parent / entry for path in paths)
            names = sorted(path.name for path in left.iterdir())
            require(names == sorted(path.name for path in right.iterdir()), 'Artifact inventory')
            for name in names:
                require((left / name).read_bytes() == (right / name).read_bytes(),
                        f'Artifact mismatch: {entry}/{name}')
            for kind, suffix in kinds.items():
                counted[kind] += sum(1 for name in names if name.endswith(suffix))
            run(['node', 'dev/lua-same.mjs', str(left)], diagnostic=b'LUA-SAME')
        # Each counter below is a file count over the compared directories.
        require(counted['wasm'] == len(cases), 'Wasm artifact count')
        require(counted['bash'] == len(cases), 'Shell artifact count')
        require(counted['metadata'] == 2 * len(cases), 'Metadata artifact count')
        require(counted['lua'] >= 1 and imports >= 1, 'Lua body or import count')
        print(f'PASS DO-ARTIFACTS pairs={len(cases)} wasm={counted["wasm"]} '
              f'bash={counted["bash"]} lua={counted["lua"]} '
              f'metadata={counted["metadata"]} imports={imports}', flush=True)
        luajit = 0
        effects = sum(1 for _entry, _expected, stored, code in cases
                      if code != 0 and stored != b'\n')
        with local.hosts(work) as (port, env):
            cli = ['redis-cli', '-h', '127.0.0.1', '-p', str(port)]
            for entry, expected, stored, code in cases:
                output = paths[0].parent / entry
                for command, host_env in [(['node', 'runtime/redis-host.mjs', str(output / 'prog.wasm'), str(port)], None),
                                          (['/bin/bash', str(output / 'prog.sh')], env)]:
                    run(cli + ['FLUSHDB'])
                    run(cli + ['SCRIPT', 'FLUSH'])
                    require(run(command, code=code, env=host_env) == expected, 'Host reply: ' + entry)
                    require(run(cli + ['GET', KEY]) == stored, 'Host effects: ' + entry)
                if code == 0:
                    require(previous.lua_run(work, output, None) == expected, 'LuaJIT reply: ' + entry)
                    luajit += 1
        refusals(work)
        # LuaJIT runs every successful Client; effects counts the faults
        # whose stored counter survived.
        require(luajit >= 1 and effects >= 1, 'Host reply or effect count')
        print(f'PASS DO-HOSTS cases={len(cases)} luajit={luajit} effects={effects}', flush=True)
        print(f'PASS DO-TESTS example={example()}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL DO-TESTS {error}', file=sys.stderr)
        sys.exit(1)
