#!/usr/bin/env python3
"""Check Stage C bodies against an owned, temporary Redis server."""
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stage_c_tests", ROOT / "dev/stage-c-tests.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def main():
    with tempfile.TemporaryDirectory(prefix="tether-c-redis-") as temporary:
        directory = Path(temporary)
        outputs = {}
        for entry, source in [("counter", "M0Spine.tet"), ("increment", "LuaCases.tet"),
                              ("readOnly", "LuaCases.tet")]:
            out = directory / entry
            checks.run([sys.executable, "-P", "dev/emit-lua.py", "--root", "examples",
                        source, "--entry", entry, "-o", str(out)])
            outputs[entry] = out
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with (directory / "redis.log").open("wb") as log:
            process = subprocess.Popen(["redis-server", "--bind", "127.0.0.1", "--port", str(port),
                                        "--save", "", "--appendonly", "no", "--daemonize", "no"],
                                       stdout=log, stderr=subprocess.STDOUT)
            (directory / "redis.pid").write_text(str(process.pid) + "\n")
            try:
                cli = ["redis-cli", "-h", "127.0.0.1", "-p", str(port)]
                for _attempt in range(100):
                    if process.poll() is not None:
                        sys.exit("FAIL LUA-REDIS server exited: " + (directory / "redis.log").read_text())
                    response = subprocess.run(cli + ["PING"], capture_output=True, timeout=2)
                    if response.returncode == 0 and response.stdout == b"PONG\n":
                        break
                    time.sleep(0.05)
                else:
                    sys.exit("FAIL LUA-REDIS server readiness")
                digests = {}
                for entry, out in outputs.items():
                    body = (out / "script.lua").read_bytes()
                    digest = checks.run(cli + ["-x", "SCRIPT", "LOAD"], data=body).strip()
                    checks.require(digest.decode() == json.loads((out / "script.json").read_text())["sha1"],
                                   "REDIS-SHA1 " + entry)
                    digests[entry] = digest.decode()

                def invoke(entry):
                    result = checks.run(cli + ["--json", "EVALSHA", digests[entry],
                                               "1", "{counter}:hits:visits"])
                    return json.loads(result)

                checks.run(cli + ["SET", "{counter}:hits:visits", "9007199254740992"])
                checks.require(invoke("counter") == "9007199254740993", "REDIS-SPINE")
                checks.run(cli + ["SET", "{counter}:hits:visits", "9007199254740992"])
                checks.require(invoke("increment") == "9007199254740993", "REDIS-INCR-BULK")
                checks.run(cli + ["SET", "{counter}:hits:visits", "9223372036854775806"])
                checks.require(invoke("increment") == "9223372036854775807", "REDIS-MAXIMUM")
                checks.require(invoke("readOnly") == "9223372036854775807", "REDIS-READ")
                checks.run(cli + ["DEL", "{counter}:hits:visits"])
                checks.require(invoke("readOnly") is None, "REDIS-NIL")
                print("PASS LUA-REDIS cases=5 sha1=3", flush=True)
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=10)
                checks.require(process.poll() is not None, "REDIS-STOP")
                print("REDIS-STOPPED owned=1", flush=True)


if __name__ == "__main__":
    main()
