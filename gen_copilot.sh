#!/usr/bin/env bash
# Generate mill-copilot.yaml from mill.yaml: the copilot-only fallback
# profile for when Claude plan usage is tight. Copilot serves the same
# model family, so the only differences are the runtime provider and
# spelling model names as copilot IDs (bare SDK aliases like "sonnet"
# don't resolve there). checks.sh fails if the generated file is stale:
#
#   ./gen_copilot.sh          # regenerate mill-copilot.yaml
#   ./gen_copilot.sh <path>   # write elsewhere (used by checks.sh drift gate)
#
set -euo pipefail
cd "$(dirname "$0")"
OUT="${1:-mill-copilot.yaml}" python3 - <<'EOF'
import os
src = open("mill.yaml").read()

subs = [
    # Runtime: same family, served by copilot.
    ("    provider: claude-agent-sdk\n    default_model: sonnet\n",
     "    provider: copilot\n    default_model: claude-sonnet-5\n"),
    # implement_model default + guidance use copilot model IDs.
    ('      default: "sonnet"\n',
     '      default: "claude-sonnet-5"\n'),
    ("Model for the implement/fix agents (bump to opus for hard chunks)",
     "Model for the implement/fix agents (bump to claude-opus-5 for hard chunks)"),
]
for old, new in subs:
    assert src.count(old) == 1, f"transform anchor drifted: {old!r}"
    src = src.replace(old, new)

banner = """\
# ============================ GENERATED FILE ============================
# mill-copilot.yaml — copilot-only fallback profile. DO NOT EDIT: edit
# mill.yaml and run ./gen_copilot.sh. Identical workflow, but every agent
# runs through the copilot provider (Claude plan usage: zero). Launch via
# `mill ... --copilot`, or point conductor at this file directly.
# ========================================================================
"""
out = os.environ["OUT"]
open(out, "w").write(banner + src)
print(f"wrote {out}")
EOF
