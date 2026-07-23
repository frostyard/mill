---
title: .mill.toml
description: Per-repository configuration reference.
group: Reference
order: 21
---

Everything repo-specific lives in a committed `.mill.toml` at the repository
root; the engine is generic. The `millify` skill generates this file, or
copy `mill.toml.example` and edit.

```toml
[gates]
chunk = [
  "make generate",
  "make format-check",
  "go vet ./...",
  "go test ./...",
]
deep = ["make docker-test"]

[context]
docs = ["AGENTS.md", "docs/architecture.md"]
skills_dir = "docs/agents/skills"

[review]
security_invariants = """
The web process must never touch privileged APIs directly — all
privileged access goes through the broker.
"""

[harvest]
allowlist = ["docs/agents/skills/", "AGENTS.md"]
```

## [gates]

`chunk` — the fast gate sequence run after every chunk (and once as the
baseline before any work). Each entry runs via `bash -c` and must exit
non-zero on failure. Order them cheapest-first: codegen, format check,
static analysis, tests. Gate commands are repo-committed and carry the same
trust as the Makefile they invoke.

`deep` — the heavyweight pre-ship gate. Best practice: point it at a single
make target that runs *every gate CI runs, in CI's order* (for example a
`make ci` / `make docker-ci` target). One target means the mill, a human
before pushing, and CI all agree about what "passing" means — no
local-green/CI-red surprises. `--no-deep` substitutes the chunk gates.

In `bash -c` pipelines remember the exit code is the last command's — use
`set -o pipefail`, and wrap `grep` filters in `{ grep ... || true; }` so an
all-clean run doesn't read as a failure.

## [context]

`docs` — files every agent reads before planning, implementing, or
reviewing. Put the canonical conventions doc (`AGENTS.md`) first; the
harvest step appends its skills pointer there.

`skills_dir` — where harvested lessons live.

## [review]

`security_invariants` — prose injected into the security reviewer's brief.
State the rules that must survive any change; the final security review
checks the whole branch against them.

## [limits]

Optional overrides for the bounded loops. Defaults: `plan_rounds = 3`,
`gate_attempts = 3`, `review_rounds = 2`. Large specifications converge
slower in adversarial plan review — an 18-chunk plan can improve on every
round and still need more than three; raise `plan_rounds` for repositories
that take big specs. Exhausting `plan_rounds` escalates to a human gate
rather than failing; the other two bounds end the run with a resumable
checkpoint.

```toml
[limits]
plan_rounds = 6
```

## [harvest]

`allowlist` — the only paths the harvest step may modify. Anything else it
touches is reverted by the harvest gate before the commit is made.
