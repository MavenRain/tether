#!/usr/bin/env python3
"""Bash 3.2, real jq, isolated curl transcripts, byte agreement and negative controls."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNS = 0
KILLED = []


def killed_by(name, gate):
    """Count every killed mutant, so the printed census cannot drift from the runs."""
    KILLED.append(name)
    print(f"KILLED {name} by {gate}", flush=True)


def require(condition, name):
    if not condition:
        sys.exit("FAIL STAGE-D " + name)


def run(argv, *, data=None, env=None, code=0, diagnostic=None):
    result = subprocess.run(argv, cwd=ROOT, input=data, env=env,
                            capture_output=True, timeout=120)
    require(result.returncode == code and (diagnostic is None or diagnostic in
            result.stdout + result.stderr), f"{argv} exit={result.returncode}\n"
            + (result.stdout + result.stderr).decode("utf-8", "replace"))
    return result


def curl_stub():
    """Run only from the test's PATH shim; log requests without credentials."""
    args = sys.argv[2:]
    request = json.loads(args[args.index("--data-binary") + 1])
    require(all(isinstance(item, str) for item in request), "POST strings")
    require("Content-Type: application/json" in args and
            "Authorization: Bearer test-token-never-printed" in args, "POST headers")
    require(args[args.index("-X") + 1] == "POST" and
            args[args.index("-X") + 2] == "http://127.0.0.1:1", "POST target")
    log = Path(os.environ["TETHER_STUB_LOG"])
    previous = log.read_text().splitlines() if log.exists() else []
    responses = json.loads(Path(os.environ["TETHER_STUB_PLAN"]).read_text())
    # Log before any refusal, so an unplanned request still reaches the request count check.
    with log.open("a") as stream:
        stream.write(json.dumps(request) + "\n")
    require(len(previous) < len(responses), "unexpected extra request")
    response = responses[len(previous)]
    if "auto_sha" in response:
        require(request[:2] == ["SCRIPT", "LOAD"], "expected SCRIPT LOAD")
        response = {"result": hashlib.sha1(request[2].encode()).hexdigest()}
    elif "exit" in response:
        sys.exit(response["exit"])
    elif "raw" in response:
        sys.stdout.write(response["raw"])
        return
    print(json.dumps(response))


def emit(directory, entry, source="ShCases.tet", *, code=0, diagnostic=None, fuel="1000000"):
    output = directory / entry
    run([sys.executable, "-P", "dev/emit-sh.py", "--root", "examples", source,
         "--entry", entry, "-o", str(output), "--fuel", fuel], code=code, diagnostic=diagnostic)
    if code:
        require(not output.exists(), "refusal wrote output " + entry)
    return output


def assignments(shell):
    return shell.split(b"# TETHER-BODIES-BEGIN\n", 1)[1].split(b"# TETHER-BODIES-END\n", 1)[0]


def lua_same(output):
    shell = (output / "prog.sh").read_bytes()
    manifest = json.loads((output / "scripts.json").read_text())
    # A manifest swap must not empty the comparison: pin it against the shell assignments.
    slots = sum(1 for i in range(len(manifest) + 1)
                if f"\nloaded{i}=0\n".encode() in assignments(shell))
    if slots != len(manifest):
        return False
    for index, artifact in enumerate(manifest):
        body = (output / (artifact["stem"] + ".lua")).read_bytes()
        extracted = run(["/bin/bash"], data=b"set -eu\n" + assignments(shell) +
                        f'printf \'%s\' "$lua{index}"\n'.encode()).stdout
        carrier = run(["node", "dev/extract-body.mjs",
                       str(output / (artifact["stem"] + ".wasm"))]).stdout
        sha = run(["node", "dev/extract-body.mjs",
                   str(output / (artifact["stem"] + ".wasm")), "scriptSha1"]).stdout
        if not (body == extracted == carrier and
                sha.decode() == artifact["sha1"] == hashlib.sha1(body).hexdigest()):
            return False
    return True


def exercise(directory, output, responses, expected=b"", *, code=0, stderr=None):
    global RUNS
    RUNS += 1
    log = directory / "requests.jsonl"
    plan = directory / "responses.json"
    log.unlink(missing_ok=True)
    plan.write_text(json.dumps(responses))
    env = dict(os.environ, PATH=str(directory / "bin") + os.pathsep + os.environ["PATH"],
               TETHER_URL="http://127.0.0.1:1", TETHER_TOKEN="test-token-never-printed",
               TETHER_STUB_LOG=str(log), TETHER_STUB_PLAN=str(plan))
    result = run(["/bin/bash", str(output / "prog.sh")], env=env, code=code)
    require(result.stdout == expected, "reply stdout " + repr(result.stdout))
    require(b"test-token-never-printed" not in result.stderr, "token leaked")
    require(stderr is None or result.stderr == stderr, "reply stderr " + repr(result.stderr))
    calls = [json.loads(row) for row in log.read_text().splitlines()] if log.exists() else []
    require(len(calls) == len(responses), "request count")
    return calls


def main():
    require(run(["jq", "--version"]).stdout.strip() == b"jq-1.6", "JQ-VERSION")
    version = run(["/bin/bash", "--version"]).stdout
    require(b"version 3.2.57" in version, "BASH-VERSION")
    print("JQ-VERSION jq-1.6 BASH-VERSION 3.2.57", flush=True)
    with tempfile.TemporaryDirectory(prefix="tether-stage-d-") as work:
        directory = Path(work)
        bindir = directory / "bin"
        bindir.mkdir()
        stub = bindir / "curl"
        # The emitted program still calls curl normally. Only this test PATH is replaced.
        stub.write_text("#!/bin/bash\nexec " + "'" + sys.executable + "' -P '" +
                        str(Path(__file__).resolve()) + "' --curl \"$@\"\n")
        stub.chmod(0o755)
        outputs = {"main": emit(directory, "main", "M0Spine.tet")}
        for entry in ("twice", "capturedReply", "quotedMain", "exactMain", "stopped"):
            outputs[entry] = emit(directory, entry)
        for output in outputs.values():
            run(["/bin/bash", "-n", str(output / "prog.sh")])
            require(lua_same(output), "LUA-SAME " + output.name)
        bodies = sum(len(json.loads((p / "scripts.json").read_text())) for p in outputs.values())
        print(f"BASH-SYNTAX ok=1 artifacts={len(outputs)}", flush=True)
        require(bodies == 6, f"body census {bodies}")
        print(f"LUA-SAME wasm=1 sh=1 bodies={bodies}", flush=True)
        load = {"auto_sha": True}
        for reply, expected in [
                ("9007199254740993", b"9007199254740993\n"),
                ("9223372036854775807", b"9223372036854775807\n"),
                ("-9223372036854775808", b"-9223372036854775808\n"),
                (42, b"42\n"), (None, b"\n"), ("", b"\n"),
                ("quotes\"' $() `x` \\ \n\n", b"quotes\"' $() `x` \\ \n\n\n"),
                ("\u0000\u00e9", b"\x00\xc3\xa9\n"),
                ([None, "9007199254740993", ["nested", 4]],
                 b'[null,"9007199254740993",["nested",4]]\n')]:
            calls = exercise(directory, outputs["main"], [load, {"result": reply}], expected)
            require([c[0] for c in calls] == ["SCRIPT", "EVALSHA"], "first load order")
            require(calls[1][2:] == ["1", "{counter}:hits:visits"], "physical key")
        calls = exercise(directory, outputs["twice"],
                         [load, {"result": "1"}, {"result": "2"}], b"2\n")
        require([c[0] for c in calls] == ["SCRIPT", "EVALSHA", "EVALSHA"], "load once")
        print("SH-LOAD-ONCE loads=1 invokes=2 steady_calls=1", flush=True)
        calls = exercise(directory, outputs["capturedReply"],
                         [load, {"result": "first\n"}, load, {"result": "second"}], b"first\n\n")
        require(calls[0][2] != calls[2][2], "distinct script cache")
        calls = exercise(directory, outputs["quotedMain"], [load, {"result": "ok"}], b"ok\n")
        require(calls[1][3] == "{counter}:hits:q\"'$(printf injected);`printf injected`\\\n", "quoted key")
        calls = exercise(directory, outputs["exactMain"], [load, {"result": "9007199254740993"}],
                         b"9007199254740993\n")
        require(calls[1][2:] == ["0"], "zero keys")
        calls = exercise(directory, outputs["twice"],
                         [load, {"error": "NOSCRIPT No matching script."},
                          {"result": "1"}, {"result": "2"}], b"2\n")
        require([c[0] for c in calls] == ["SCRIPT", "EVALSHA", "EVAL", "EVALSHA"], "fallback order")
        require(calls[2][1] == calls[0][2] and calls[2][2:] == calls[1][2:], "fallback bytes and keys")
        manifest = json.loads((outputs["twice"] / "scripts.json").read_text())
        carrier = run(["node", "dev/extract-body.mjs", str(outputs["twice"] /
                      (manifest[0]["stem"] + ".wasm"))]).stdout
        require(calls[0][2].encode() == carrier, "transmitted LUA-SAME")
        exercise(directory, outputs["main"], [load, {"result": "NOSCRIPT text"}], b"NOSCRIPT text\n")
        for response in [True, {}, 9007199254740992, 1.5, [True], [9007199254740993]]:
            exercise(directory, outputs["main"], [load, {"result": response}], code=4)
        fault_text = b"TETHER Network or Http fault\n"
        for response, diagnostic in [({}, None), ({"error": "BUSY fixture"}, b"BUSY fixture\n"),
                                     ({"error": "OOM fixture"}, b"OOM fixture\n"),
                                     ({"error": "ERR fixture"}, b"ERR fixture\n"),
                                     ({"error": "NOSCRIPTISH fixture"}, b"NOSCRIPTISH fixture\n"),
                                     ({"result": "x", "error": "NOSCRIPT"}, None),
                                     ({"result": "x", "extra": 0}, None), ({"error": None}, None),
                                     ({"raw": "not json"}, None),
                                     ({"raw": '{"result":1}\n{"result":2}'}, None),
                                     ({"exit": 22}, fault_text), ({"exit": 7}, fault_text)]:
            exercise(directory, outputs["main"], [load, response], code=4, stderr=diagnostic)
        exercise(directory, outputs["main"], [load, {"error": "NOSCRIPT"},
                 {"error": "NOSCRIPT"}], code=4)
        for response, diagnostic in [({"result": "0" * 40}, None),
                                     ({"error": "BUSY"}, b"BUSY\n"),
                                     ({"error": "ERR Error compiling script"},
                                      b"ERR Error compiling script\n"),
                                     ({"error": "NOAUTH Authentication required."},
                                      b"NOAUTH Authentication required.\n"),
                                     ({"exit": 22}, fault_text)]:
            exercise(directory, outputs["main"], [response], code=4, stderr=diagnostic)
        exercise(directory, outputs["stopped"], [], code=4, stderr=b"TETHER Client fault\n")
        print(f"PASS SH-REPLIES runs={RUNS}", flush=True)
        refusals = [("higherMain", b"SH-FIRST-ORDER"), ("constructed", b"SH-FIRST-ORDER"),
                    ("partialMain", b"SH-FIRST-ORDER"), ("inlineMain", b"SH-FIRST-ORDER"),
                    ("branched", b"SH-FIRST-ORDER"),
                    ("nulMain", b"SH-KEY-TEXT"), ("wrongClient", b"mismatch")]
        for entry, diagnostic in refusals:
            emit(directory, entry, code=2, diagnostic=diagnostic)
        emit(directory, "missing", code=2, diagnostic=b"unbound")
        # The checker exhausts the shared budget before the static walk, so pin its own message.
        emit(directory, "budget", source="M0Spine.tet", code=2,
             diagnostic=b"CHECK budget", fuel="0")
        # The M1 List move prelude consumes 84753 polls before the static walk.
        # Leave six polls for that walk, preserving the printer's own refusal.
        walk = directory / "budget-walk"
        run([sys.executable, "-P", "dev/emit-sh.py", "--root", "examples", "M0Spine.tet",
             "--entry", "main", "-o", str(walk), "--fuel", "84759"],
            code=2, diagnostic=b"SH-BUDGET")
        require(not walk.exists(), "refusal wrote output budget-walk")
        before = (outputs["main"] / "prog.sh").read_bytes()
        run([sys.executable, "-P", "dev/emit-sh.py", "--root", "examples", "M0Spine.tet",
             "-o", str(outputs["main"])], code=2, diagnostic=b"File exists")
        require((outputs["main"] / "prog.sh").read_bytes() == before, "existing output changed")
        print(f"PASS SH-REFUSALS cases={len(refusals) + 4}", flush=True)
        header = before.split(b"# TETHER-BODIES-BEGIN\n", 1)[0]
        env = dict(os.environ, TETHER_URL="http://127.0.0.1:1", TETHER_TOKEN="test")
        probes = [b'env_json=\'{"result":true}\'\nenvelope\nprintf "accepted\\n"\n',
                  b'envelope() { kind=boolean; }\nreply "{}"\nprintf "accepted\\n"\n']
        arm = b"    *) exit 4 ;;\n"
        require(header.count(arm) == len(probes), "case default census")
        for index, probe in enumerate(probes):
            require(run(["/bin/bash"], data=header + probe, env=env, code=4).stdout == b"", "default control")
            pieces = header.split(arm)
            mutant = arm.join(pieces[:index + 1]) + arm.join(pieces[index + 1:])
            run(["/bin/bash", "-n"], data=mutant)
            require(run(["/bin/bash"], data=mutant + probe, env=env).stdout == b"accepted\n", "default mutant survived")
            run(["/bin/bash"], data=header + probe, env=env, code=4)
            killed_by(f"DROP-CASE-{index}", "reply comparison")
        target = outputs["main"] / "prog.sh"
        require(before.count(b"local function bytes(s)") == 1, "body mutation anchor")
        target.write_bytes(before.replace(b"local function bytes(s)", b"local function bytes(t)", 1))
        require(not lua_same(outputs["main"]), "body mutant survived")
        target.write_bytes(before)
        require(lua_same(outputs["main"]), "body restore")
        killed_by("SH-BODY-BYTE", "LUA-SAME")
        # Require the newly implemented printer and enforce its existing bound.
        root = directory / "integrity"
        # bin carries its own trusted-lines bound, so the copy needs it too.
        for name in ("bin", "dev", "print", "store", "runtime", "vendor/kanon/lib", "vendor/kanon/wasm"):
            shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
        gate = [sys.executable, "-P", str(root / "dev/trusted-lines.py")]
        run(gate)
        printer = root / "print/sh.ml"
        original = printer.read_bytes()
        printer.unlink()
        run(gate, code=1, diagnostic=b"TRUSTED-LINES FAIL")
        printer.write_bytes(original)
        run(gate)
        killed_by("MISSING-SH", "TRUSTED-LINES")
        printer.write_bytes(original + b"\n" * 241)
        run(gate, code=1, diagnostic=b"FAIL")
        printer.write_bytes(original)
        run(gate)
        killed_by("SH-BOUND", "TRUSTED-LINES")
        require(len(KILLED) == 5, f"mutant census {KILLED}")
        print(f"PASS STAGE-D-MUTATIONS killed={len(KILLED)} restored=1", flush=True)
    print("PASS STAGE-D-TESTS")


if __name__ == "__main__":
    if sys.argv[1:] and sys.argv[1] == "--curl":
        curl_stub()
    else:
        main()
