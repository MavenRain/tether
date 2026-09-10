"""Exercise Stage A gates on a disposable copy, including a rebuilt mutant."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(root, *args, env=None):
    return subprocess.run(args, cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, check=False, env=env)


def gate(root, action, env=None):
    return run(root, sys.executable, "-P", "dev/foundation.py", action, str(root), env=env)


def broken_tool(directory, name):
    """A PATH where one tool exists and fails, as a missing tool would."""
    path = Path(directory) / f"stub-{name}"
    path.mkdir(exist_ok=True)
    script = path / name
    script.write_text("#!/bin/sh\nexit 127\n")
    script.chmod(0o755)
    return {**os.environ, "PATH": f"{path}:{os.environ['PATH']}"}


def killed(names, name, action, result, reason):
    """A kill is the expected reason, never the exit code and the leg alone."""
    required = (reason,) if isinstance(reason, str) else tuple(reason)
    if result.returncode != 1 or f"{action.upper()} FAIL" not in result.stdout:
        print(f"MUTANT SURVIVED {name}: {result.stdout}")
        return False
    missing = [text for text in required if text not in result.stdout]
    if missing:
        print(f"WRONG REASON {name}: expected {missing!r}, read: {result.stdout}")
        return False
    names.append(name)
    print(f"KILLED {name} exit=1")
    return True


def main():
    # Include Git metadata so HEAD and the staged gitlink remain independent
    # of the original checkout. Relative submodule gitdirs survive this copy.
    with tempfile.TemporaryDirectory(prefix="tether-stage-a-") as directory:
        root = Path(directory) / "repo"
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            "_build", ".kanon-exec", ".kanon-wait", ".gatework", "__pycache__"))
        binary = Path("_build/default/vendor/kanon/bin/kanon.exe")
        # Only dev/r0-count.sh builds this target, so a tree that never ran
        # the gate ladder holds no binary. The battery names that as a control
        # failure instead of raising FileNotFoundError over a copy.
        if not (ROOT / binary).is_file():
            print(f"CONTROL FAIL missing build {binary}: run sh dev/stage-a.sh first")
            return 1
        (root / binary).parent.mkdir(parents=True)
        shutil.copy2(ROOT / binary, root / binary)
        for action in ("carry", "count", "audit"):
            result = gate(root, action)
            if result.returncode != 0:
                print(f"CONTROL FAIL {action}: {result.stdout}")
                return 1
        scored = []
        cases = [
            ("PIN-BYTE", "carry", "dev/PIN", lambda data: b"3" + data[1:],
             "dev/PIN differs from ratified pin"),
            ("VENDOR-BYTE", "carry", "vendor/kanon/runtime/run.mjs", lambda data: data + b"\n",
             "tracked vendor file differs from pin: ['runtime/run.mjs']"),
            ("COPY-BYTE", "carry", "runtime/reactor.kan", lambda data: data + b"\n",
             "carried bytes differ: runtime/reactor.kan"),
            ("MISSING-FILE", "carry", "vendor/kanon/wasm/emit.ml", lambda data: None,
             "tracked vendor file differs from pin: ['wasm/emit.ml']"),
            ("IGNORED-EXTRA", "carry", "vendor/kanon/lib/extra.o", lambda data: b"extra\n",
             "carried inventory differs: ['lib/extra.o']"),
            ("SURFACE-EXTRA", "carry", "vendor/kanon/surface/extra.ml", lambda data: b"let extra = 1\n",
             "files in the submodule worktree are not listed by the pin: ['surface/extra.ml']"),
            ("NAMED-PATCH", "carry", "dev/PATCHES/unruled.patch", lambda data: b"patch\n",
             "M0 requires zero named patches"),
            ("R0-ROW", "count", "SPEC.md", lambda data: data.replace(b"formers 2:", b"formers 3:"),
             "SPEC counts differ from inherited block"),
            ("REFUSAL-CITATION", "audit", "SPEC.md", lambda data: data.replace(b"`lib/rules.ml:952`", b"`lib/rules.ml:953`"),
             "refusal citation is not an audited site"),
            # The anchor leg reads the pin sources, so a moved refusal site
            # must fail even while SPEC.md is untouched.
            ("ANCHOR-MOVED", "audit", "vendor/kanon/lib/rules.ml",
             lambda data: data.replace(b'let mu_ran_word : string = "a right former',
                                       b'let mu_ran_word : string = "A right former'),
             "refusal site moved: lib/rules.ml:952"),
            # SPEC.md hard wraps, so the appended sentence wraps too.
            ("UNCITED-NAMING", "audit", "SPEC.md",
             lambda data: data + b"\nKey and Tag are namings, not\nadditional Kan formers.\n",
             "naming or refusal statements differ from the ruling: "
             "['Key and Tag are namings, not additional Kan formers.']"),
            # A keyword list reads three phrases only, so a naming that wraps
            # over a paragraph break, a naming that wraps over two list items
            # and a rephrased admission are read as claim sentences too.
            ("BLANK-WRAP-NAMING", "audit", "SPEC.md",
             lambda data: data + b"\nKey and Tag are namings, not\n\nadditional Kan formers.\n",
             "naming or refusal statements differ from the ruling: "
             "['Key and Tag are namings, not additional Kan formers.']"),
            ("LIST-WRAP-NAMING", "audit", "SPEC.md",
             lambda data: data + b"\n- `SNu` is allowed after M0 and\n- carries no refusal.\n",
             "naming or refusal statements differ from the ruling: "
             "['`SNu` is allowed after M0 and']"),
            ("REPHRASED-ADMISSION", "audit", "SPEC.md",
             lambda data: data + b"\n`SPar` is accepted at M0.\n",
             "naming or refusal statements differ from the ruling: "
             "['`SPar` is accepted at M0.']"),
            # A refusal that uses a state verb instead of the copula, and a
            # naming of a name no ruled row mentions.
            ("NONCOPULA-REFUSAL", "audit", "SPEC.md",
             lambda data: data + b"\n`SPar` stays refused after M0.\n",
             "refusal with no citation: `SPar` stays refused after M0."),
            ("UNTOKENED-NAMING", "audit", "SPEC.md",
             lambda data: data + b"\nKey and Tag are namings.\n",
             "naming or refusal statements differ from the ruling: "
             "['Key and Tag are namings.']"),
            # A negation reverses a ruled refusal. Without the negation
            # adverbs the sentence is no claim sentence and is never read.
            ("NEGATED-REFUSAL", "audit", "SPEC.md",
             lambda data: data + b"\n`SNu` is never refused.\n",
             "refusal with no citation: `SNu` is never refused."),
            ("MODAL-PERMISSION", "audit", "SPEC.md",
             lambda data: data + b"\nNested `Op (Script A)` cannot be nested.\n",
             "naming or refusal statements differ from the ruling: "
             "['Nested `Op (Script A)` cannot be nested.']"),
            # A cited range names a refusal body, so its start line is
            # anchored as its end line is.
            ("CITATION-START", "audit", "vendor/kanon/lib/rules.ml",
             lambda data: data.replace(b"let mu_form_ran (_ops : 'c ops)",
                                       b"let mu_form_ran (_opx : 'c ops)"),
             "refusal site moved: lib/rules.ml:1083"),
            ("POSITIVITY-START", "audit", "vendor/kanon/lib/positivity.ml",
             lambda data: data.replace(b"let rec positive (names : string list)",
                                       b"let rec positive (namez : string list)"),
             "refusal site moved: lib/positivity.ml:85"),
            # A missing or broken inherited script fails with the same first
            # line, so the leaking site is required too.
            ("SHAPE-LEAK", "audit", "vendor/kanon/lib/eval.ml", lambda data: data + b"\n(* SNu *)\n",
             ("inherited shape isolation audit failed", "lib/eval.ml:", "R0-AUDIT FAIL")),
        ]
        for name, action, rel, mutate, reason in cases:
            path = root / rel
            original = path.read_bytes() if path.exists() else None
            changed = mutate(original)
            if changed is None:
                path.unlink()
            else:
                path.write_bytes(changed)
            result = gate(root, action)
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)
            if not killed(scored, name, action, result, reason):
                return 1

        # A gate that reads a tool must fail when the tool fails, and not read
        # an empty result as a pass.
        result = gate(root, "audit", env=broken_tool(directory, "rg"))
        if not killed(scored, "NO-RG", "audit", result, "rg is on PATH but exits 127"):
            return 1

        index = root / ".git/index"
        original_index = index.read_bytes()
        wrong = "3c2e6e6831a0b2cf3107fa4aad392606109a2bcf"
        changed = run(root, "git", "update-index", "--cacheinfo", f"160000,{wrong},vendor/kanon")
        if changed.returncode != 0:
            print(f"CONTROL FAIL gitlink mutation: {changed.stdout}")
            return 1
        result = gate(root, "carry")
        index.write_bytes(original_index)
        if not killed(scored, "GITLINK", "carry", result, "staged gitlink differs from pin"):
            return 1

        # The HEAD comparison is the other half of the gitlink leg. The ref is
        # moved to the parent commit, so no worktree file and no build changes.
        vendor = root / "vendor/kanon"
        parent = run(vendor, "git", "rev-parse", "HEAD^")
        if parent.returncode != 0:
            print(f"CONTROL FAIL parent commit: {parent.stdout}")
            return 1
        head = parent.stdout.strip()
        moved = run(vendor, "git", "update-ref", "--no-deref", "HEAD", head)
        if moved.returncode != 0:
            print(f"CONTROL FAIL head mutation: {moved.stdout}")
            return 1
        result = gate(root, "carry")
        run(vendor, "git", "update-ref", "--no-deref", "HEAD",
            "2c2e6e6831a0b2cf3107fa4aad392606109a2bcf")
        if not killed(scored, "HEAD-SHA", "carry", result, "submodule HEAD differs from pin"):
            return 1

        # The pin carries one nested gitlink. Git reports a nested gitlink as a
        # changed path, so both nested legs are scored here and each one must
        # print its own reason instead of the whole tree diff reason.
        inner = "vendor/tot"
        inside = vendor / inner
        aside = vendor / "vendor/tot-moved-by-the-battery"
        os.rename(inside, aside)
        result = gate(root, "carry")
        os.rename(aside, inside)
        if not killed(scored, "NESTED-MISSING", "carry", result,
                      f"nested submodule directory missing: {inner}"):
            return 1

        # The pinned nested checkout is not initialized, so the battery
        # initializes it at a commit of its own and reads the HEAD leg.
        for args in (("init", "-q"), ("commit", "-q", "--allow-empty", "-m", "battery")):
            step = run(inside, "git", *args, env={**os.environ,
                                                  "GIT_AUTHOR_NAME": "battery",
                                                  "GIT_AUTHOR_EMAIL": "battery@invalid",
                                                  "GIT_COMMITTER_NAME": "battery",
                                                  "GIT_COMMITTER_EMAIL": "battery@invalid"})
            if step.returncode != 0:
                print(f"CONTROL FAIL nested init: {step.stdout}")
                return 1
        result = gate(root, "carry")
        shutil.rmtree(inside / ".git")
        if not killed(scored, "NESTED-HEAD", "carry", result,
                      f"nested submodule HEAD differs from pin: {inner}"):
            return 1

        # The unlisted leg drops every worktree path under a nested gitlink,
        # so a file dropped in an uninitialized nested checkout is its own
        # case and the emptiness leg prints its own reason.
        extra = inside / "lib/tot.ml"
        extra.parent.mkdir(parents=True)
        extra.write_text("let extra = 1\n")
        result = gate(root, "carry")
        shutil.rmtree(extra.parent)
        if not killed(scored, "NESTED-EXTRA", "carry", result,
                      f"nested submodule directory is not empty: {inner}"):
            return 1

        # An initialized nested checkout at the pinned head holds files that
        # the missing, HEAD and emptiness legs never read, so the battery
        # produces that state and mutates a file inside it. The clone reads
        # the nested URL of the pin and never the origin of the submodule.
        clone = run(root, "git", "-c", "protocol.file.allow=always", "-C",
                    str(vendor), "submodule", "update", "--init", inner)
        if clone.returncode != 0:
            print(f"CONTROL FAIL nested init: {clone.stdout}")
            return 1
        control = gate(root, "carry")
        if control.returncode != 0:
            print(f"CONTROL FAIL initialized nested checkout: {control.stdout}")
            return 1
        leak = inside / "extra_leak.ml"
        leak.write_text("let extra = 1\n")
        result = gate(root, "carry")
        leak.unlink()
        if not killed(scored, "NESTED-UNLISTED", "carry", result,
                      "files in the nested submodule are not listed by the pin: "
                      f"['{inner}/extra_leak.ml']"):
            return 1

        tracked = inside / "dune-project"
        original = tracked.read_bytes()
        tracked.write_bytes(original + b"\n")
        result = gate(root, "carry")
        tracked.write_bytes(original)
        if not killed(scored, "NESTED-TRACKED", "carry", result,
                      "tracked file in the nested submodule differs from pin: "
                      f"['{inner}/dune-project']"):
            return 1
        # Restore the uninitialized state the pin ships.
        shutil.rmtree(inside)
        inside.mkdir()

        # This gate must rebuild instead of trusting the copied old executable.
        shape = root / "vendor/kanon/lib/shape.ml"
        original = shape.read_bytes()
        changed = original.replace(b'"SMu"; "SNu" ]', b'"SMu"; "SNu"; "SExtra" ]')
        if changed == original:
            print("CONTROL FAIL shape mutation did not match")
            return 1
        shape.write_bytes(changed)
        result = run(root, "sh", "dev/r0-count.sh")
        shape.write_bytes(original)
        if result.returncode != 1 or "built counts differ" not in result.stdout or "shapes declared 6:" not in result.stdout:
            print(f"MUTANT SURVIVED SIXTH-SHAPE: {result.stdout}")
            return 1
        scored.append("SIXTH-SHAPE")
        print("KILLED SIXTH-SHAPE exit=1 rebuilt=1")

        # The eight frozen checksum entries are a gate leg of their own, so one
        # hashed artifact is changed and the battery reads the failing row.
        denominator = root / "dev/tcc-denominator.sh"
        original = denominator.read_bytes()
        denominator.write_bytes(original + b"\n")
        result = run(root, "sh", "dev/stage-a.sh")
        denominator.write_bytes(original)
        if result.returncode == 0 or "dev/tcc-denominator.sh: FAILED" not in result.stdout:
            print(f"MUTANT SURVIVED DENOMINATOR-BYTE: {result.stdout}")
            return 1
        scored.append("DENOMINATOR-BYTE")
        print(f"KILLED DENOMINATOR-BYTE exit={result.returncode}")

        # The trusted-line leg counts through awk under set -u alone, so the
        # battery must read the printed line and not the exit code alone.
        result = run(root, "sh", "dev/stage-a.sh", env=broken_tool(directory, "awk"))
        if result.returncode != 1 or "TRUSTED-LINES FAIL unexpected line" not in result.stdout:
            print(f"MUTANT SURVIVED NO-AWK: {result.stdout}")
            return 1
        scored.append("NO-AWK")
        print("KILLED NO-AWK exit=1")

        # The checksum check reads the rows the manifest holds, so a manifest
        # with a row removed passes over the artifact it no longer names.
        manifest = root / "dev/DENOMINATORS.sha256"
        original = manifest.read_bytes()
        manifest.write_bytes(b"".join(original.splitlines(True)[:7]))
        result = run(root, "sh", "dev/stage-a.sh")
        manifest.write_bytes(original)
        if result.returncode != 1 or "DENOMINATORS FAIL the manifest holds 7 rows" not in result.stdout:
            print(f"MUTANT SURVIVED MANIFEST-ROW: {result.stdout}")
            return 1
        scored.append("MANIFEST-ROW")
        print("KILLED MANIFEST-ROW exit=1")

        # A row count alone leaves a swap open: one row replaced by a copy of
        # another row keeps eight rows and drops one artifact from the check.
        rows = original.splitlines(True)
        manifest.write_bytes(b"".join(rows[:7] + [rows[0]]))
        result = run(root, "sh", "dev/stage-a.sh")
        manifest.write_bytes(original)
        if result.returncode != 1 or "DENOMINATORS FAIL the manifest names" not in result.stdout:
            print(f"MUTANT SURVIVED MANIFEST-SWAP: {result.stdout}")
            return 1
        scored.append("MANIFEST-SWAP")
        print("KILLED MANIFEST-SWAP exit=1")

        # A broken shasum ends the ladder at exit 127 with no reason line.
        result = run(root, "sh", "dev/stage-a.sh", env=broken_tool(directory, "shasum"))
        if result.returncode != 1 or "DENOMINATORS FAIL the checksum check failed" not in result.stdout:
            print(f"MUTANT SURVIVED NO-SHASUM: {result.stdout}")
            return 1
        scored.append("NO-SHASUM")
        print("KILLED NO-SHASUM exit=1")

        # The scoped build is a gate leg, so a broken dune must print the
        # count reason and not the shell message at exit 127.
        result = run(root, "sh", "dev/stage-a.sh", env=broken_tool(directory, "dune"))
        if result.returncode != 1 or "R0-COUNT FAIL the scoped dune build failed" not in result.stdout:
            print(f"MUTANT SURVIVED NO-DUNE: {result.stdout}")
            return 1
        scored.append("NO-DUNE")
        print("KILLED NO-DUNE exit=1")

        # The other face of the same leg: dune absent from PATH altogether.
        empty = Path(directory) / "empty-path"
        empty.mkdir(exist_ok=True)
        result = run(root, "/bin/sh", "dev/r0-count.sh",
                     env={**os.environ, "PATH": str(empty)})
        if result.returncode != 1 or "R0-COUNT FAIL dune is not on PATH" not in result.stdout:
            print(f"MUTANT SURVIVED NO-DUNE-PATH: {result.stdout}")
            return 1
        scored.append("NO-DUNE-PATH")
        print("KILLED NO-DUNE-PATH exit=1")

        result = run(root, "sh", "dev/stage-a.sh")
        if result.returncode != 0:
            print(f"CONTROL FAIL restored gates: {result.stdout}")
            return 1
        print(f"PASS STAGE-A-MUTATIONS killed={len(scored)} survived=0 restored=1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
