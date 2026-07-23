#!/usr/bin/env bash
# Run the mill (frostyard's spec→PR harness) against the current repository.
#
#   mill <issue#|spec-file> [--auto] [--web] [--no-pr] [--no-deep] [--fresh]
#
#   --auto     unattended: auto-approve human gates (conductor --skip-gates)
#   --web      run in background with the conductor web dashboard (gates are
#              answered in the browser or via `conductor gate respond`)
#   --no-pr    never push or open a PR, keep the branch local
#   --no-deep  final gate runs the chunk gates instead of [gates].deep
#   --fresh    discard an existing worktree for this source and start over
#
# Requires a .mill.toml at the repo root (run the millify skill to create
# one) and the conductor CLI with the claude-agent-sdk provider installed.
#
# The claude-agent-sdk provider ignores working_dir, so process cwd is the
# isolation boundary: this script creates .worktrees/mill-<id> on branch
# mill/<id> and runs conductor from inside it. The main checkout is never
# touched; a failed run is cleaned up with:  git worktree remove --force <dir>
set -euo pipefail

MILL_HOME=$(cd "$(dirname "$(realpath "$0")")" && pwd)

usage() { grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -12; exit 1; }

[ $# -ge 1 ] || usage
SOURCE="$1"; shift
AUTO=0 OPEN_PR=true DEEP=true FRESH=0 WEB=0
for arg in "$@"; do
    case "$arg" in
        --auto)    AUTO=1 ;;
        --no-pr)   OPEN_PR=false ;;
        --no-deep) DEEP=false ;;
        --fresh)   FRESH=1 ;;
        --web)     WEB=1 ;;
        *) usage ;;
    esac
done

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
[ -f .mill.toml ] || { echo "no .mill.toml in $ROOT — run the millify skill to set this repo up" >&2; exit 1; }

if [[ "$SOURCE" =~ ^[0-9]+$ ]]; then
    ID="issue-$SOURCE"
else
    [ -f "$SOURCE" ] || { echo "spec file not found: $SOURCE" >&2; exit 1; }
    SOURCE=$(realpath "$SOURCE")
    ID=$(basename "$SOURCE" | tr -c 'a-zA-Z0-9' '-' | sed 's/-*$//' | cut -c1-40)
fi
WT="$ROOT/.worktrees/mill-$ID"
BRANCH="mill/$ID"

if [ "$FRESH" = 1 ] && [ -d "$WT" ]; then
    git worktree remove --force "$WT"
    git branch -D "$BRANCH" 2>/dev/null || true
fi

if [ -d "$WT" ]; then
    echo "→ reusing existing worktree $WT (use --fresh to start over)"
else
    git worktree add "$WT" -b "$BRANCH"
fi

cd "$WT"
FLAGS=()
[ "$AUTO" = 1 ] && FLAGS+=(--skip-gates)
[ "$WEB" = 1 ] && FLAGS+=(--web-bg)

exec conductor run "$MILL_HOME/mill.yaml" \
    -i "source=$SOURCE" \
    -i "deep_gate=$DEEP" \
    -i "open_pr=$OPEN_PR" \
    --log-file auto \
    "${FLAGS[@]}"
