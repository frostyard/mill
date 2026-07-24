#!/usr/bin/env bash
# Fast engine self-checks. Run locally before pushing; CI runs it too.
set -euo pipefail
cd "$(dirname "$0")"

fail() { echo "✗ $1" >&2; exit 1; }

# 1. Every script step must resolve the helper via workflow.dir, never a
#    repo-relative path (the engine runs from its install dir).
for wf in mill.yaml spec_prep.yaml; do
    grep -q '"scripts/mill_state.py"' "$wf" \
        && fail "$wf references scripts/mill_state.py — use {{ workflow.dir }}/mill_state.py"
done
echo "✓ script paths use workflow.dir"

# 2. Python syntax.
python3 -c "import ast; ast.parse(open('mill_state.py').read())"
echo "✓ mill_state.py parses"

# 3. Shell syntax.
bash -n mill.sh && bash -n spec_prep.sh && bash -n install.sh
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
    ('{"response": "prose\n```json\n{\"verdict\": \"pass\", \"findings\": []}\n```"}', "pass"),
    ('{"result": "```json\n{\"verdict\": \"needs_clarification\"}\n```"}', "needs_clarification"),
]
for text, want in cases:
    got, _ = m.parse_review(text)
    assert got == want, f"parse_review({text!r}) = {got!r}, want {want!r}"
print("✓ parse_review contract holds")
EOF

# 5. spec-prep severity-routing contract: only blocking/high block; medium/low
#    converge; the round budget bounds the loop; unparseable never converges.
python3 - <<'EOF'
import importlib.util
spec = importlib.util.spec_from_file_location("ms", "mill_state.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
H = lambda s: {"severity": s, "detail": "x"}
cases = [
    # (verdict, findings, rounds, budget) -> action
    ("needs_clarification", [H("medium"), H("low")], 0, 5, "finalize"),
    ("needs_clarification", [H("high")],             0, 5, "harden"),
    ("needs_clarification", [H("blocking"), H("medium")], 1, 5, "harden"),
    ("needs_clarification", [H("high")],             5, 5, "stall"),
    ("sound", [], 0, 5, "finalize"),
    ("unparseable", [], 0, 5, "harden"),   # no findings but unparseable != converged
]
for verdict, findings, rounds, budget, want in cases:
    action, _, _ = m._prep_decision(verdict, findings, rounds, budget)
    assert action == want, f"_prep_decision({verdict},{[f['severity'] for f in findings]},{rounds},{budget}) = {action}, want {want}"
print("✓ spec-prep routing contract holds")
EOF

# 6. conductor schema validation, when conductor is available.
if command -v conductor >/dev/null 2>&1; then
    conductor validate mill.yaml >/dev/null
    conductor validate spec_prep.yaml >/dev/null
    echo "✓ conductor validate (mill.yaml, spec_prep.yaml)"
else
    echo "- conductor not installed; skipping schema validation"
fi

echo "all checks passed"
