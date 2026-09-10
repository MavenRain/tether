#!/bin/zsh
# spike-pin.sh ROOT PIN
# Prototype of Stage A dev/carry-check.sh (R-Q3, R-M0-2).
# ROOT is a repository that holds the submodule vendor/kanon.  PIN is a file
# with one full sha and a newline.  Three checks, then one printed line:
#   1. the submodule HEAD equals the PIN content;
#   2. git -C /Users/oobi/Documents/kanon rev-parse PIN equals the PIN content;
#   3. every file under lib/, wasm/ and runtime/ of the submodule checkout is
#      byte identical to `git -C /Users/oobi/Documents/kanon show PIN:PATH`,
#      and the checkout holds no file those three trees do not list.
# Prints `PIN <short> unlisted=0 lib=N wasm=N runtime=N` and exits 0, or
# `PIN FAIL <reason>` and exits 1.  Usage errors exit 4.
set -eu

KANON='/Users/oobi/Documents/kanon'

case "$#" in
  2) ;;
  *) printf 'usage: spike-pin.sh ROOT PIN\n' >&2; exit 4 ;;
esac

ROOT="$1"
PIN_PATH="$2"
SUB="$ROOT/vendor/kanon"

fail() { printf 'PIN FAIL %s\n' "$*"; exit 1; }

[ -f "$PIN_PATH" ] || fail "no PIN file at $PIN_PATH"
[ -d "$SUB" ] || fail "no submodule checkout at $SUB"

PIN="$(tr -d '\n' < "$PIN_PATH")"
printf '%s' "$PIN" | rg -q '^[0-9a-f]{40}$' || fail "PIN content is not a 40-hex sha: $PIN"
SHORT="$(printf '%s' "$PIN" | cut -c1-7)"

# Check 1: submodule HEAD.
SUB_HEAD="$(git -C "$SUB" rev-parse HEAD 2>/dev/null || true)"
[ "$SUB_HEAD" = "$PIN" ] || fail "submodule HEAD $SUB_HEAD differs from PIN $PIN"

# Check 2: the main checkout resolves the PIN to itself (reads the object, never the tree).
MAIN_PIN="$(git -C "$KANON" rev-parse --verify "$PIN^{commit}" 2>/dev/null || true)"
[ "$MAIN_PIN" = "$PIN" ] || fail "main checkout rev-parse of PIN gave '$MAIN_PIN'"

# Check 3: byte identity of lib/, wasm/ and runtime/ against `git show PIN:PATH`.
LISTED="$(git -C "$KANON" ls-tree -r --name-only "$PIN" -- lib wasm runtime | sort)"
[ -n "$LISTED" ] || fail "pin lists no file under lib, wasm or runtime"

# The loop runs in the main shell, so `fail` exits the script and its line
# reaches stdout.  zsh ties the lowercase name `path` to PATH, so the loop
# variable is `rel`.
while IFS= read -r rel; do
  [ -n "$rel" ] || continue
  [ -f "$SUB/$rel" ] || fail "missing in checkout: $rel"
  cmp -s "$SUB/$rel" <(git -C "$KANON" show "$PIN:$rel") || fail "differs from pin: $rel"
done < <(printf '%s\n' "$LISTED")

LIB_N="$(printf '%s\n' "$LISTED" | rg -c '^lib/' || printf '0')"
WASM_N="$(printf '%s\n' "$LISTED" | rg -c '^wasm/' || printf '0')"
RUNTIME_N="$(printf '%s\n' "$LISTED" | rg -c '^runtime/' || printf '0')"

# Unlisted: files present in the checkout under the three directories that the
# pin tree does not list.  At Stage 0 dev/PATCHES is empty, so the count must be 0.
PRESENT="$(fd -t f -H . "$SUB/lib" "$SUB/wasm" "$SUB/runtime" | sd "^$SUB/" '' | sort)"
UNLISTED="$(comm -13 <(printf '%s\n' "$LISTED") <(printf '%s\n' "$PRESENT") | rg -c . || printf '0')"
[ "$UNLISTED" -eq 0 ] || fail "unlisted=$UNLISTED $(comm -13 <(printf '%s\n' "$LISTED") <(printf '%s\n' "$PRESENT") | head -3 | tr '\n' ' ')"

[ "$LIB_N" -gt 0 ] || fail "empty tree lib=$LIB_N"
[ "$WASM_N" -gt 0 ] || fail "empty tree wasm=$WASM_N"
[ "$RUNTIME_N" -gt 0 ] || fail "empty tree runtime=$RUNTIME_N"

printf 'PIN %s unlisted=%s lib=%s wasm=%s runtime=%s\n' "$SHORT" "$UNLISTED" "$LIB_N" "$WASM_N" "$RUNTIME_N"
