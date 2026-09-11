#!/usr/bin/env python3
"""Executable Stage C checks, including mutations of emitted artifacts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(argv, *, data=None, ok=True, diagnostic=None):
    result = subprocess.run(argv, cwd=ROOT, input=data, capture_output=True, timeout=120)
    output = result.stdout + result.stderr
    if (result.returncode == 0) != ok or (diagnostic and diagnostic not in output):
        sys.exit(f"FAIL STAGE-C {argv} exit={result.returncode}\n"
                 + output.decode("utf-8", "replace"))
    return result.stdout


def require(condition, name):
    if not condition:
        sys.exit("FAIL STAGE-C " + name)


def lua_string(data):
    return '"' + "".join(f"\\{b:03d}" for b in data) + '"'


SANDBOX_RUNS = 0


def sandbox(directory, artifact, value=None, next_value=b"9007199254740993", fault=None,
            *, ok=True, diagnostic=None, keys=None, get_fault=None):
    global SANDBOX_RUNS
    info = json.loads((artifact / "script.json").read_text())
    if keys is None:
        keys = [bytes.fromhex(key) for key in info["keys_hex"]]
    config = directory / "config.lua"
    fields = ["keys={" + ",".join(lua_string(key) for key in keys) + "}"]
    for name, data in [("value", value), ("next", next_value), ("fault", fault),
                       ("getFault", get_fault)]:
        if data is not None:
            fields.append(name + "=" + lua_string(data))
    config.write_text("return {" + ",".join(fields) + "}\n")
    SANDBOX_RUNS += 1
    return run(["luajit", "-joff", "dev/lua-sandbox.lua", str(artifact / "script.lua"),
                str(config)], ok=ok, diagnostic=diagnostic)


def lua_same(output):
    """Re-run the LUA-SAME leg over one artifact directory and answer the result."""
    body = (output / "script.lua").read_bytes()
    carrier = run(["node", "dev/extract-body.mjs", str(output / "body.wasm")])
    digest = run(["node", "dev/extract-body.mjs", str(output / "body.wasm"), "scriptSha1"])
    return carrier == body and digest == hashlib.sha1(body).hexdigest().encode()


def emitted(directory, source, entry, flags):
    output = directory / entry
    run([sys.executable, "-P", "dev/emit-lua.py", "--root", "examples", source,
         "--entry", entry, "-o", str(output)])
    body = (output / "script.lua").read_bytes()
    metadata = json.loads((output / "script.json").read_text())
    require(body and not body.endswith(b"\n") and b"\r" not in body
            and not body.startswith(b"\xef\xbb\xbf"), "CANONICAL " + entry)
    require(metadata["sha1"] == hashlib.sha1(body).hexdigest(), "SHA1 " + entry)
    require(metadata["no_writes"] == flags, "FLAGS " + entry)
    require(body.startswith(b"#!lua flags=no-writes\n") == flags, "FLAGS-BODY " + entry)
    run(["luajit", "-bl", str(output / "script.lua")])
    run(["wasm-tools", "validate", str(output / "body.wasm")])
    require(lua_same(output), "LUA-SAME " + entry)
    digest = run(["node", "dev/extract-body.mjs", str(output / "body.wasm"), "scriptSha1"])
    require(digest == metadata["sha1"].encode(), "WASM-SHA1 " + entry)
    return output


def bulk(data):
    return b"bulk:" + data.hex().encode()


def main():
    # Padding boundaries, multiple blocks, embedded NUL and all byte values.
    vectors = [b"", b"abc", b"a" * 55, b"a" * 56, b"a" * 63, b"a" * 64,
               b"a" * 65, b"a" * 1000, bytes(range(256))]
    for data in vectors:
        digest = run(["_build/default/dev/sha1_probe.exe"], data=data).strip()
        require(digest == hashlib.sha1(data).hexdigest().encode(), "SHA1-VECTOR")
    print(f"PASS SHA1 vectors={len(vectors)}", flush=True)
    with tempfile.TemporaryDirectory(prefix="tether-stage-c-") as work:
        directory = Path(work)
        artifacts = {"counter": emitted(directory, "M0Spine.tet", "counter", False)}
        for entry in ("readOnly", "increment", "captured", "classify", "branchWrite",
                      "exact", "maximum", "minimum", "binary", "replies"):
            artifacts[entry] = emitted(directory, "LuaCases.tet", entry,
                                       entry not in ("increment", "captured", "branchWrite"))
        print(f"LUA-SYNTAX parsed={len(artifacts)} of={len(artifacts)}", flush=True)
        print(f"LUA-SAME wasm=1 bodies={len(artifacts)}", flush=True)
        checks = [
            ("counter", None, bulk(b"9007199254740993"), b"INCR,GET,GET"),
            ("readOnly", None, b"nil", b"GET"),
            ("readOnly", b"\x00\xff", bulk(b"\x00\xff"), b"GET"),
            ("increment", b"9007199254740992", bulk(b"9007199254740993"), b"INCR,GET"),
            ("captured", b"before", bulk(b"before"), b"GET,INCR,GET"),
            ("classify", None, b"status:6d697373696e67", b"GET"),
            ("classify", b"payload", bulk(b"payload"), b"GET"),
            ("branchWrite", None, bulk(b"9007199254740993"), b"GET,INCR,GET"),
            ("branchWrite", b"kept", bulk(b"kept"), b"GET"),
            ("exact", None, bulk(b"9007199254740993"), b""),
            ("maximum", None, bulk(b"9223372036854775807"), b""),
            ("minimum", None, bulk(b"-9223372036854775808"), b""),
            ("binary", None, bulk(b"\x00\xff\"'\\\n\r123"), b""),
            ("replies", None, b"array:[nil," + bulk(b"9007199254740993")
             + b",bulk:62,status:4f4b,err:4552522066697874757265,array:[]]", b""),
        ]
        observed = {}
        for name, value, expected, calls in checks:
            answer = sandbox(directory, artifacts[name], value)
            require(answer == expected + b"\nCALLS " + calls + b"\n", "REPLY " + name)
            observed.setdefault(name, set()).add(b"INCR" in calls)
        answer = sandbox(directory, artifacts["increment"], fault=b"ERR overflow")
        require(answer == b"err:455252206f766572666c6f77\nCALLS INCR\n", "OVERFLOW-REPLY")
        # A failing command becomes a Reply error on the read after a write and
        # on the read-only path, so neither arm aborts the script.
        fault_reply = b"err:" + b"ERR read".hex().encode()
        answer = sandbox(directory, artifacts["increment"], b"9007199254740992",
                         get_fault=b"ERR read")
        require(answer == fault_reply + b"\nCALLS INCR,GET\n", "WRITE-READ-FAULT-REPLY")
        answer = sandbox(directory, artifacts["readOnly"], b"payload", get_fault=b"ERR read")
        require(answer == fault_reply + b"\nCALLS GET\n", "READ-FAULT-REPLY")
        sandbox(directory, artifacts["counter"], keys=[], ok=False,
                diagnostic=b"LUA-KEY missing declared key")
        print(f"NO-GLOBALS leaked=0 runs={SANDBOX_RUNS}", flush=True)
        # The census is derived: the flag comes from the emitted metadata and a
        # branch writer is the artifact observed both writing and not writing.
        declared = {name: json.loads((output / "script.json").read_text())["no_writes"]
                    for name, output in artifacts.items()}
        read_only = sum(1 for flag in declared.values() if flag)
        branch_write = sum(1 for name, flag in declared.items()
                           if not flag and observed.get(name) == {True, False})
        write = sum(1 for flag in declared.values() if not flag) - branch_write
        require(read_only + write + branch_write == len(artifacts), "FLAGS-CENSUS")
        print(f"FLAGS read-only={read_only} write={write} branch-write={branch_write}",
              flush=True)
        for entry, fuel, diagnostic in [("wrongResult", "1000000", b"mismatch"),
                                        ("missing", "1000000", b"LUA-ENTRY"),
                                        ("readOnly", "0", b"budget")]:
            output = directory / ("refused-" + entry)
            run([sys.executable, "-P", "dev/emit-lua.py", "--root", "examples", "LuaCases.tet",
                 "--entry", entry, "--fuel", fuel, "-o", str(output)], ok=False, diagnostic=diagnostic)
            require(not output.exists(), "REFUSAL-WROTE-OUTPUT")
        print("PASS LUA-REFUSALS cases=3", flush=True)
        # Keep the positive controls and restore every mutated artifact.
        target = artifacts["counter"] / "script.lua"
        original = target.read_bytes()
        require(original.count(b"local function bytes(s)") == 1, "LOCAL-ANCHOR")
        target.write_bytes(original.replace(b"local function bytes(s)", b"function bytes(s)", 1))
        run(["luajit", "-bl", str(target)])
        sandbox(directory, artifacts["counter"], ok=False, diagnostic=b"NO-GLOBALS write bytes")
        print("KILLED DROP-LOCAL by NO-GLOBALS", flush=True)
        target.write_bytes(original)
        sandbox(directory, artifacts["counter"])
        # A dropped local whose name is one the sandbox binds must fail too.
        require(original.count(b"local function text(b)") == 1, "STUB-ANCHOR")
        target.write_bytes(original.replace(b"local function text(b)", b"function type(b)", 1))
        run(["luajit", "-bl", str(target)])
        sandbox(directory, artifacts["counter"], ok=False, diagnostic=b"NO-GLOBALS write type")
        print("KILLED STUB-GLOBAL by NO-GLOBALS", flush=True)
        target.write_bytes(original)
        sandbox(directory, artifacts["counter"])
        # The extraction must come from the Wasm carrier alone, so a changed Lua
        # file leaves the extracted bytes untouched and breaks both comparisons.
        carrier_file = artifacts["counter"] / "body.wasm"
        before = run(["node", "dev/extract-body.mjs", str(carrier_file)])
        target.write_bytes(original + b"\n")
        require(run(["node", "dev/extract-body.mjs", str(carrier_file)]) == before,
                "CARRIER-INDEPENDENT")
        require(not lua_same(artifacts["counter"]), "BODY-BYTE-MUTATION")
        print("KILLED BODY-BYTE by LUA-SAME", flush=True)
        target.write_bytes(original)
        require(lua_same(artifacts["counter"]), "RESTORED-LUA-SAME")
        print("PASS STAGE-C-MUTATIONS killed=3 restored=1", flush=True)
    print("PASS STAGE-C-TESTS")


if __name__ == "__main__":
    main()
