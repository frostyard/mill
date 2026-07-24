#!/usr/bin/env bash
# Install (or update) the frostyard mill.
#
#   curl -sSfL https://raw.githubusercontent.com/frostyard/mill/main/install.sh | sh
#
# Installs to ~/.local/share/frostyard-mill, symlinks the `mill` and
# `spec-prep` commands into ~/.local/bin, and (if ~/.claude exists) links the
# millify skill so Claude Code can set up new repositories.
set -eu

REPO="https://github.com/frostyard/mill.git"
HOME_DIR="${MILL_INSTALL_DIR:-$HOME/.local/share/frostyard-mill}"
BIN_DIR="$HOME/.local/bin"

if [ -d "$HOME_DIR/.git" ]; then
    echo "→ updating $HOME_DIR"
    git -C "$HOME_DIR" pull --ff-only
else
    echo "→ cloning into $HOME_DIR"
    git clone --depth 1 "$REPO" "$HOME_DIR"
fi

mkdir -p "$BIN_DIR"
ln -sf "$HOME_DIR/mill.sh" "$BIN_DIR/mill"
ln -sf "$HOME_DIR/spec_prep.sh" "$BIN_DIR/spec-prep"
chmod +x "$HOME_DIR/mill.sh" "$HOME_DIR/spec_prep.sh"
echo "✓ mill -> $BIN_DIR/mill"
echo "✓ spec-prep -> $BIN_DIR/spec-prep"

if [ -d "$HOME/.claude" ]; then
    mkdir -p "$HOME/.claude/skills"
    ln -sfn "$HOME_DIR/skills/millify" "$HOME/.claude/skills/millify"
    echo "✓ millify skill -> ~/.claude/skills/millify"
fi

command -v conductor >/dev/null 2>&1 || cat <<'MSG'
! conductor not found. Install it, then the claude-agent-sdk provider:
    curl -sSfL https://aka.ms/conductor/install.sh | sh
    uv tool install --force 'conductor-cli[claude-agent-sdk] @ git+https://github.com/microsoft/conductor.git@v0.1.25'
MSG
echo "Done. In a repo with a .mill.toml:  mill <issue#|spec.md>"
