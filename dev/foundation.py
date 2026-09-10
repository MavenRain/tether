"""Stage A integrity gates. Read the local submodule only, never its origin."""

import difflib
import re
import subprocess
import sys
from pathlib import Path

PIN = "2c2e6e6831a0b2cf3107fa4aad392606109a2bcf"
CARRIED = {
    "dev/bench.sh": "dev/bench.sh",
    "dev/inherited/r0-audit.sh": "dev/r0-audit.sh",
    "dev/inherited/trusted-lines.sh": "dev/trusted-lines.sh",
    "runtime/reactor.kan": "runtime/reactor.kan",
}
# Build outputs and capture directories of the submodule. Dune compiles no
# file under them, and the same names are ignored by the root .gitignore and
# skipped by the mutation runner copy.
BUILD_DIRECTORIES = {"_build", ".gatework", "__pycache__", ".git",
                     ".kanon-exec", ".kanon-wait"}
CLAIM = re.compile(r"are namings, not additional Kan formers|is refused|is admitted")
# A keyword list reads three phrases only, so the whole prose surface is read
# as well. A sentence is a claim sentence when it links any subject to a
# naming, refusal, admission or permission word, with a copula or with one of
# the state verbs stay, remain, become and continue, or when it grants a
# nesting permission. The subject is not restricted to a ruled token, so a
# claim about an unruled name is a claim sentence too.
COPULA = (r"(?:is|are|was|were|stays?|remains?|becomes?"
          r"|(?:continues?|shall|will|must)\s+(?:to\s+)?be)")
# A negation reverses a ruled refusal, so the adverbs that carry a negation
# stand between the copula and the state word, and modal negation is read as
# its own form. Without them "is never refused" and "cannot be nested" are no
# claim sentences at all and pass the audit unread.
ADVERB = (r"(?:(?:not|never|no\s+longer|nor|neither|only|still|always|now"
          r"|already|again|ever|yet|also|therefore|instead)\s+)*")
STATE = (r"(?:naming|namings|refused|admitted|accepted|allowed|permitted"
         r"|denied|rejected|forbidden|banned|supported)")
MODAL = (r"(?:cannot|can\s+not|(?:can|could|may|might|must|shall|will|would"
         r"|does|do|did|need)\s+not)")
NESTS = r"(?:nest|nests|nested|appear|occur|stand|be\s+used|be\s+nested)"
VERB = re.compile(r"\b" + COPULA + r"\s+" + ADVERB + r"(?:an?\s+)?" + STATE + r"\b"
                  r"|\bmay\s+" + ADVERB + NESTS + r"\b"
                  r"|\b" + MODAL + r"\s+(?:be\s+)?(?:an?\s+)?"
                  r"(?:" + STATE + r"|" + NESTS + r")\b")
MARKER = re.compile(r"^([-*+]\s+|[0-9]+\.\s+)")
CITATION = re.compile(r"`(lib/[A-Za-z0-9_]+\.ml):([0-9]+)(?:-([0-9]+))?`")
COUNTED = (("formers", "formers"), ("schema", "schema constructors"),
           ("shapes", "shapes declared"), ("admitted", "shapes admitted"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.returncode, result.stdout, result.stderr


def command(*args):
    """Keep the failing output: an exit code alone names no defect."""
    code, output, errors = run(list(args))
    require(code == 0, "command failed with exit {0}: {1}\n{2}{3}".format(
        code, " ".join(args), output.decode(errors="replace"), errors.decode(errors="replace")))
    return output


def git(root, *args):
    return command("git", "-C", str(root), *args)


def tool(name, *args):
    """A gate that reads a tool fails when the tool is absent or broken."""
    try:
        code, _, errors = run([name, *args])
    except OSError as error:
        raise ValueError(f"{name} is not usable: {error}")
    require(code == 0, f"{name} is on PATH but exits {code}: {errors.decode(errors='replace')}")


def plain_file(path):
    require(path.is_file() and not path.is_symlink(), f"missing or nonregular: {path}")
    return path.read_bytes()


def worktree_files(vendor):
    """Every regular file of the submodule worktree outside its build outputs."""
    found = set()
    for path in vendor.rglob("*"):
        rel = path.relative_to(vendor)
        if BUILD_DIRECTORIES.intersection(rel.parts):
            continue
        require(not path.is_symlink(), f"symlink in submodule worktree: {rel.as_posix()}")
        if path.is_file():
            found.add(rel.as_posix())
    return found


def carry(root):
    vendor = root / "vendor/kanon"
    require(plain_file(root / "dev/PIN") == (PIN + "\n").encode(), "dev/PIN differs from ratified pin")
    require((vendor / ".git").exists(), "submodule is not initialized")
    require(git(vendor, "rev-parse", "--show-toplevel").decode().strip() == str(vendor), "submodule is not initialized")
    require(git(vendor, "rev-parse", "HEAD").decode().strip() == PIN, "submodule HEAD differs from pin")
    require(git(root, "ls-files", "--stage", "vendor/kanon").decode() ==
            f"160000 {PIN} 0\tvendor/kanon\n", "staged gitlink differs from pin")
    modules = plain_file(root / ".gitmodules")
    require(git(root, "show", ":.gitmodules") == modules, ".gitmodules is not staged")
    for key, value in (("path", "vendor/kanon"), ("url", "/Users/oobi/Documents/kanon")):
        actual = command("git", "config", "--file", str(root / ".gitmodules"),
                         "--get-all", f"submodule.vendor/kanon.{key}")
        require(actual.decode() == value + "\n", f"submodule {key} differs from ruling")
    patches = root / "dev/PATCHES"
    require(patches.is_dir() and not patches.is_symlink(), "dev/PATCHES missing or symlinked")
    require(sorted(p.name for p in patches.iterdir()) == [".gitkeep"] and
            plain_file(patches / ".gitkeep") == b"", "M0 requires zero named patches")
    # The pin also carries nested gitlinks. The pin lists such a path once,
    # while the worktree holds every file of the nested checkout, so a
    # recursive submodule init must not read as an unlisted file. Git reports
    # a nested gitlink as a changed path when its checkout is gone or its HEAD
    # moved, so the nested legs run before the whole tree diff and that diff
    # drops the nested names. Each nested fault then prints its own reason.
    entries = [record.split("\t", 1) for record in
               git(vendor, "ls-tree", "-r", "-z", PIN).decode().rstrip("\0").split("\0") if record]
    listed = {name for _, name in entries}
    nested = {name: meta.split(" ")[2] for meta, name in entries if meta.startswith("160000 ")}
    for inner, head in sorted(nested.items()):
        inside = vendor / inner
        require(inside.is_dir() and not inside.is_symlink(), f"nested submodule directory missing: {inner}")
        initialized = (inside / ".git").exists()
        require(not initialized or
                git(inside, "rev-parse", "HEAD").decode().strip() == head,
                f"nested submodule HEAD differs from pin: {inner}")
        # The unlisted leg below drops every worktree path under a nested
        # gitlink, so an uninitialized nested checkout must hold no file.
        require(initialized or not any(inside.iterdir()),
                f"nested submodule directory is not empty: {inner}")
        if initialized:
            # An initialized nested checkout holds files that the legs above
            # never read, so the diff and the unlisted leg run inside it
            # against its own pinned head.
            inner_changed = [name for name in
                             git(inside, "diff", "--no-ext-diff", "--name-only", head, "--").decode().split("\n")
                             if name]
            require(not inner_changed,
                    f"tracked file in the nested submodule differs from pin: "
                    f"{[inner + '/' + name for name in inner_changed]}")
            inner_extra = sorted(
                name for name in git(inside, "ls-files", "--others", "-z").decode().rstrip("\0").split("\0")
                if name and not BUILD_DIRECTORIES.intersection(Path(name).parts))
            require(not inner_extra,
                    f"files in the nested submodule are not listed by the pin: "
                    f"{[inner + '/' + name for name in inner_extra]}")
    changed = [name for name in
               git(vendor, "diff", "--no-ext-diff", "--name-only", PIN, "--").decode().split("\n")
               if name and name not in nested]
    require(not changed, f"tracked vendor file differs from pin: {changed}")
    expected = set(git(vendor, "ls-tree", "-r", "--name-only", "-z", PIN,
                       "--", "lib", "wasm", "runtime").decode().rstrip("\0").split("\0"))
    actual = set()
    for directory in ("lib", "wasm", "runtime"):
        base = vendor / directory
        require(base.is_dir() and not base.is_symlink(), f"missing or symlinked {directory}")
        for path in base.rglob("*"):
            require(not path.is_symlink(), f"symlink in carried tree: {path}")
            if path.is_file():
                actual.add(path.relative_to(vendor).as_posix())
    require(actual == expected, f"carried inventory differs: {sorted(actual ^ expected)}")
    for rel in sorted(expected):
        require(plain_file(vendor / rel) == git(vendor, "show", f"{PIN}:{rel}"), f"vendor bytes differ: {rel}")
    for destination, source in CARRIED.items():
        require(plain_file(root / destination) == git(vendor, "show", f"{PIN}:{source}"), f"carried bytes differ: {destination}")
    # The scoped build also compiles every module of bin/ and surface/, so the
    # whole worktree is compared against the pin and not the carried three.
    unlisted = sorted(name for name in worktree_files(vendor) - listed
                      if not any(name.startswith(inner + "/") for inner in nested))
    require(not unlisted, f"files in the submodule worktree are not listed by the pin: {unlisted}")
    print(f"PIN {PIN[:7]} unlisted={len(unlisted)}")
    print(f"CARRY files={len(expected) + len(CARRIED)} diff={len(changed)} "
          f"vendor={len(expected)} copies={len(CARRIED)}")


def count_block(text):
    blocks = re.findall(r"^## R0 counts\n(?:(?!^## ).)*?^```\n(.*?)^```$", text, re.M | re.S)
    require(len(blocks) == 1, "SPEC needs exactly one R0 counts block")
    return blocks[0]


def count_fields(block):
    """Read the printed numbers out of the block instead of restating them."""
    rows = dict(row.split(": ", 1) for row in block.rstrip("\n").split("\n"))
    fields = []
    for field, prefix in COUNTED:
        keys = [key for key in rows if key.startswith(prefix + " ")]
        require(len(keys) == 1, f"the R0 block misses the {prefix} row")
        value = keys[0].split(" ")[-1]
        names = rows[keys[0]].split()
        require(str(len(names)) == value, f"the {prefix} row states {value} and lists {len(names)}")
        fields.append(f"{field}={value}")
    return " ".join(fields)


def count(root):
    documented = count_block(plain_file(root / "SPEC.md").decode())
    inherited = count_block(git(root / "vendor/kanon", "show", f"{PIN}:SPEC.md").decode())
    require(documented == inherited, "SPEC counts differ from inherited block")
    built = command(str(root / "_build/default/vendor/kanon/bin/kanon.exe"), "spec-count").decode()
    require(built == documented, "built counts differ:\n" + "".join(difflib.unified_diff(
        documented.splitlines(True), built.splitlines(True), fromfile="SPEC", tofile="kernel")))
    print("R0-COUNT " + count_fields(built))


def claim_sentences(text):
    """Sentences, not lines. SPEC.md hard wraps, so a claim spans lines."""
    units, current, fenced = [], [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            units.append(" ".join(current))
            current = []
            fenced = not fenced
        elif fenced:
            units.append(stripped)
        elif not stripped:
            # A blank line ends no sentence, so a claim wrapped across a
            # paragraph break stays one unit.
            continue
        elif stripped.startswith("#"):
            units.append(" ".join(current))
            current = []
        elif MARKER.match(stripped) or stripped.startswith("|"):
            units.append(" ".join(current))
            current = [MARKER.sub("", stripped)]
        else:
            current.append(stripped)
    units.append(" ".join(current))
    return [sentence.strip() for unit in units
            for sentence in re.split(r"(?<=\.)\s+", unit) if sentence.strip()]


def audit(root):
    spec = plain_file(root / "SPEC.md").decode()
    rows = [
        "Script, Client and folds are namings, not additional Kan formers.",
        "`Ran_U U` is refused: `lib/rules.ml:952` and `lib/rules.ml:1083-1086`.",
        "Nested `Op (Script A)` is refused: `lib/positivity.ml:85-90`.",
        "`SPar` is refused: `lib/rules.ml:1429`.",
        "`SNu` is refused: `lib/rules.ml:1432`.",
    ]
    # A cited range names a refusal body, not its last line, so every line of
    # a ruled range is anchored. With the end line alone the body above it can
    # be replaced by comments while the audit prints ok.
    anchors = [
        ("lib/rules.ml", 952, 'let mu_ran_word : string = "a right former at a mu shape arrives at M2"'),
        ("lib/rules.ml", 1083, "let mu_form_ran (_ops : 'c ops) (_ctx : 'c) (_s : Term.t Shape.t) (_diagram : Term.t)"),
        ("lib/rules.ml", 1084, "    ~(expected : Level.t option) : (Level.t, Error.t) result ="),
        ("lib/rules.ml", 1085, "  let _ = expected in"),
        ("lib/rules.ml", 1086, "  Error (Error.Not_yet mu_ran_word)"),
        ("lib/rules.ml", 1429, "  | Shape.SPar (_, _) -> Error (Error.Not_yet spar_word)"),
        ("lib/rules.ml", 1432, "  | Shape.SNu (_, _) -> Error (Error.Not_yet snu_word)"),
        ("lib/positivity.ml", 85, "let rec positive (names : string list) (t : Term.t) : (unit, Error.t) result ="),
        ("lib/positivity.ml", 86, "  match t with"),
        ("lib/positivity.ml", 87, "  | Term.Lan (s, d) ->"),
        ("lib/positivity.ml", 88, "      if is_member names (Shape.family s) then"),
        ("lib/positivity.ml", 89, "        Result.bind (absent_list names (Shape.payload s)) (fun () -> absent names d)"),
        ("lib/positivity.ml", 90, "      else absent names t"),
    ]
    # Every sentence of SPEC.md that states a naming, a refusal, an admission
    # or a nesting permission is a ruled one, and no other such sentence
    # stands. A naming with no citation is a gate failure, and a citation
    # outside the audited sites is a gate failure (M0 plan, R0 audit).
    stated = {unit for unit in claim_sentences(spec)
              if CLAIM.search(unit) or VERB.search(unit)}
    # The citation legs read the sentences of the document, not the rows, so a
    # moved citation fails on its own reason and not on the equality below.
    sites = {(rel, line) for rel, line, _ in anchors}
    for row in sorted(stated):
        if "refused" in row:
            cited = CITATION.findall(row)
            require(cited, f"refusal with no citation: {row}")
            for rel, start, end in cited:
                # Both ends of a range are audited sites, so a citation that
                # covers unanchored lines fails here.
                require((rel, int(start)) in sites and (rel, int(end or start)) in sites,
                        f"refusal citation is not an audited site: {row}")
    require(stated == set(rows),
            f"naming or refusal statements differ from the ruling: {sorted(stated ^ set(rows))}")
    for rel, line, source in anchors:
        lines = plain_file(root / "vendor/kanon" / rel).decode().splitlines()
        require(len(lines) >= line and lines[line - 1] == source, f"refusal site moved: {rel}:{line}")
    # The inherited script reports a leak through ripgrep. Without a working
    # ripgrep it prints OK over an empty read, so the tool is read first.
    tool("rg", "--version")
    code, output, errors = run(["zsh", "-f", str(root / "dev/inherited/r0-audit.sh"),
                                str(root / "vendor/kanon")])
    require(code == 0 and output == b"R0-AUDIT OK\n", "inherited shape isolation audit failed:\n" +
            output.decode(errors="replace") + errors.decode(errors="replace"))
    print("R0-AUDIT ok")


def main():
    actions = {"carry": carry, "count": count, "audit": audit}
    if len(sys.argv) != 3 or sys.argv[1] not in actions:
        print("usage: foundation.py carry|count|audit ROOT", file=sys.stderr)
        return 4
    action, root = sys.argv[1], Path(sys.argv[2]).resolve()
    try:
        actions[action](root)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"{action.upper()} FAIL {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
