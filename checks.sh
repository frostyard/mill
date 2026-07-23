#!/usr/bin/env bash
# Fast engine self-checks. Run locally before pushing; CI runs it too.
set -euo pipefail
cd "$(dirname "$0")"

fail() { echo "✗ $1" >&2; exit 1; }

# 1. Every script step must resolve the helper via workflow.dir, never a
#    repo-relative path (the engine runs from its install dir).
grep -q '"scripts/mill_state.py"' mill.yaml \
    && fail 'mill.yaml references scripts/mill_state.py — use {{ workflow.dir }}/mill_state.py'
echo "✓ script paths use workflow.dir"

# 2. Python syntax.
python3 -c "import ast; ast.parse(open('mill_state.py').read())"
echo "✓ mill_state.py parses"

# 3. Shell syntax.
bash -n mill.sh && bash -n install.sh
echo "✓ shell scripts parse"

# 4. parse_review normalization contract.
python3 - <<'EOF'
import importlib.util
spec = importlib.util.spec_from_file_location("ms", "mill_state.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
cases = [
    ('{"verdict": "approve", "objections": []}', "approve"),
    ('x\n```json\n{"verdict": "revise"}\n```', "revise"),
    ('{"verdict": {"decision": "approve"}}', "approve"),
    ('```json\n{"verdict": {"verdict": "pass"}}\n```', "pass"),
    ("verdict: FAIL because", "fail"),
    ("garbage", "unparseable"),
]
for text, want in cases:
    got, _ = m.parse_review(text)
    assert got == want, f"parse_review({text!r}) = {got!r}, want {want!r}"
print("✓ parse_review contract holds")
EOF

# 5. conductor schema validation, when conductor is available.
if command -v conductor >/dev/null 2>&1; then
    conductor validate mill.yaml >/dev/null
    echo "✓ conductor validate"
else
    echo "- conductor not installed; skipping schema validation"
fi

echo "all checks passed"
