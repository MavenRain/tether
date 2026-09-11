"""Own a temporary Redis server and REST twin, including failed startup cleanup."""
from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import select
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def hosts(work):
    processes = []
    with (work / 'redis.log').open('wb') as log, (work / 'rest.log').open('wb') as rest_log:
        try:
            # Retry a bind race, and verify that readiness belongs to our child.
            for _attempt in range(20):
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1', 0))
                    port = probe.getsockname()[1]
                child = subprocess.Popen(['redis-server', '--bind', '127.0.0.1', '--port', str(port),
                                          '--save', '', '--appendonly', 'no', '--daemonize', 'no'],
                                         stdout=log, stderr=log)
                processes.append(child)
                (work / 'redis.pid').write_text(str(child.pid) + '\n')
                ready = False
                for _poll in range(100):
                    if child.poll() is not None:
                        break
                    info = subprocess.run(['redis-cli', '-h', '127.0.0.1', '-p', str(port), 'INFO', 'server'],
                                          capture_output=True, timeout=2)
                    if info.returncode == 0 and f'process_id:{child.pid}\r\n'.encode() in info.stdout:
                        ready = child.poll() is None
                        break
                    time.sleep(0.05)
                if ready:
                    break
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=5)
            else:
                raise ValueError('Redis readiness timeout')
            env = dict(os.environ, TETHER_REDIS_PORT=str(port), TETHER_TOKEN=secrets.token_hex(24),
                       TETHER_REST_PORT='0', TETHER_REST_LOG=str(work / 'requests.jsonl'))
            twin = subprocess.Popen(['node', str(ROOT / 'runtime/rest-twin.mjs')], env=env,
                                    stdout=subprocess.PIPE, stderr=rest_log)
            processes.append(twin)
            if not select.select([twin.stdout], [], [], 10)[0]:
                raise ValueError('REST readiness timeout')
            line = twin.stdout.readline().decode().strip()
            if not line.startswith('REST-UP port='):
                raise ValueError('REST startup failed')
            rest_port = int(line.partition('=')[2])
            if not 0 < rest_port <= 65535:
                raise ValueError('REST invalid port')
            env['TETHER_URL'] = f'http://127.0.0.1:{rest_port}/'
            yield port, env
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                if process.stdout is not None:
                    process.stdout.close()
