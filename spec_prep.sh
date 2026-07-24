#!/usr/bin/env bash
# Pre-flight spec hardening (frostyard mill). Harden a spec to a millable state
# BEFORE spending planning tokens, then feed the result to the mill:
#
#   spec-prep <issue#|spec-file> [--web] [--fresh] [--dest=PATH]
#
#   --web        run in background with the conductor web dashboard
#   --fresh      discard any existing .mill-prep state and start over
#   --dest=PATH  where to write the hardened spec
#                (default: .mill-prep/spec.hardened.md)
#
# It reviews the spec against source truth, then a hardener agent rewrites it to
# resolve blocking/high findings, looping until none remain (medium/low become
# recorded interpretations). Genuine product decisions with no source-truth
# answer are made conservatively and logged to .mill-prep/spec_decisions.json;
# supply authoritative answers in .mill-prep/spec_answers.md to steer them.
#
# On success it prints the hardened spec path. Implement it with:
#   mill .mill-prep/spec.hardened.md
#
# There is NO worktree and NO baseline: spec-prep only reads source truth and
# rewrites its own .mill-prep/spec.md (self-ignored, never touches tracked
# files). Requires a .mill.toml at the repo root and the conductor CLI.
set -euo pipefail

MILL_HOME=$(cd "$(dirname "$(realpath "$0")")" && pwd)

usage() { grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -20; exit 1; }

[ $# -ge 1 ] || usage
SOURCE="$1"; shift
WEB=0 FRESH=0 DEST=""
for arg in "$@"; do
    case "$arg" in
        --web)     WEB=1 ;;
        --fresh)   FRESH=1 ;;
        --dest=*)  DEST="${arg#--dest=}" ;;
        *) usage ;;
    esac
done

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
[ -f .mill.toml ] || { echo "no .mill.toml in $ROOT — run the millify skill to set this repo up" >&2; exit 1; }

# spec-prep state lives in its own dir so it never collides with an
# implementation run's .mill in the same checkout.
export MILL_DIR=.mill-prep
[ -n "$DEST" ] || DEST="$MILL_DIR/spec.hardened.md"

if [[ "$SOURCE" =~ ^[0-9]+$ ]]; then
    : # issue number, passed through as-is
else
    [ -f "$SOURCE" ] || { echo "spec file not found: $SOURCE" >&2; exit 1; }
    SOURCE=$(realpath "$SOURCE")
fi

# Refuse a second spec-prep in the same checkout — two would share .mill-prep
# and corrupt each other's state. Liveness is the source of truth: a conductor
# already running spec_prep.yaml with this repo root as its cwd. (Runs in OTHER
# repos are unaffected — never blanket-stop conductor; it is cross-project.)
for pid in $(pgrep -f 'conductor run.*spec_prep.yaml' 2>/dev/null || true); do
    [ "$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)" = "$ROOT" ] || continue
    echo "a spec-prep run is already active in $ROOT (pid $pid)." >&2
    echo "wait for it to finish or stop that pid; do not run two at once." >&2
    exit 1
done

[ "$FRESH" = 1 ] && rm -rf "$MILL_DIR"

FLAGS=()
[ "$WEB" = 1 ] && FLAGS+=(--web-bg)

exec conductor run "$MILL_HOME/spec_prep.yaml" \
    -i "source=$SOURCE" \
    -i "dest=$DEST" \
    --log-file auto \
    "${FLAGS[@]}"
