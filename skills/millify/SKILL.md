---
name: millify
description: Set up a repository for the frostyard mill (spec→PR harness) — generate .mill.toml from the repo's build system, seed the agent skills directory, and wire cross-agent surfaces (CLAUDE.md, .github/copilot-instructions.md, .agents, GEMINI.md). Use when the user asks to millify a repo, set up the mill, or onboard a repository to the mill.
---

# Millify a repository

Goal: after this skill runs, `mill <issue#|spec.md>` works in this repository
and every major agent ecosystem (Claude Code, GitHub Copilot, Gemini,
AGENTS.md-standard tools) sees the same conventions and learned skills.

Work from the repository root. Make no behavioral code changes.

## 1. Establish the canonical conventions doc

- If `AGENTS.md` exists, it is canonical — leave its content alone.
- If not, create a minimal `AGENTS.md`: how to build, test, and lint; any
  generated files that must never be hand-edited; repository invariants an
  agent must not break. Derive it from README, Makefile/justfile/package
  scripts, and CI configs — do not invent rules.

## 2. Generate .mill.toml

Inspect the repo (Makefile, justfile, package.json, CI workflows) and write
`.mill.toml` with these sections (see `mill.toml.example` next to this skill
for the reference shape):

- `[gates] chunk` — the fastest command sequence proving the tree is healthy:
  codegen (if any), format check, static analysis, unit tests. Each entry is
  run via `bash -c` and must exit non-zero on failure. Prefer the repo's own
  make/just targets over raw tool invocations.
- `[gates] deep` — the heavyweight pre-ship gate. Strongly prefer a single
  target that mirrors CI exactly (every job CI runs, in CI's order). If the
  repo has no such target, offer to create one (e.g. `make ci` derived from
  the CI workflow definitions) and document it in the conventions doc —
  local green must mean CI green. If none exists and the user declines,
  repeat the chunk gates.
- `[context] docs` — AGENTS.md first, then any architecture docs an agent
  should read before working (grep for AI/agent-oriented docs).
- `[context] skills_dir` — `docs/agents/skills` unless the repo has an
  established equivalent.
- `[review] security_invariants` — the repo's non-negotiable security rules,
  written as prose. If unclear, ask the user rather than guessing.
- `[harvest] allowlist` — the skills dir plus AGENTS.md.

Validate: `python3 <path-to-this-skill>/../../mill_state.py` is not needed —
instead run `mill --help` availability check and `python3 -c "import
tomllib; tomllib.load(open('.mill.toml','rb'))"`.

## 3. Seed the skills directory

- Create `<skills_dir>/` with a `.gitkeep` if empty.
- Append to `AGENTS.md` (if not already present) a "Learned agent skills"
  section: read every file in the skills dir before planning, implementing,
  or reviewing; skills are binding; new ones arrive via the mill's harvest
  step and are reviewed in PRs.

## 4. Wire cross-agent surfaces (symlinks)

Create these relative symlinks so every agent ecosystem reads the same
canonical files (skip any that already exist as real files — report those to
the user instead of overwriting):

| Link | Target | Consumer |
|---|---|---|
| `CLAUDE.md` | `AGENTS.md` | Claude Code |
| `GEMINI.md` | `AGENTS.md` | Gemini CLI |
| `.github/copilot-instructions.md` | `../AGENTS.md` | GitHub Copilot |
| `.agents` | `docs/agents` (parent of skills_dir) | `.agents/`-convention tools |

Use `ln -s` with relative targets so links survive clones. `git add` them —
git stores symlinks portably (Windows checkouts need `core.symlinks`; note
this in the commit message if the repo has Windows contributors).

## 5. Finish

- Ensure `.worktrees/` is gitignored (the mill runs in worktrees there).
- Show the user a summary: generated `.mill.toml` (ask them to sanity-check
  the gate commands — wrong gates are the main failure mode), created links,
  and the launch command: `mill <issue#> --no-pr` for a first supervised run.
- Do not commit or push unless the user asks.
