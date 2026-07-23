# mill

frostyard's spec→PR harness: takes a complete specification (a GitHub issue
or a markdown file) and puts it through the mill using
[microsoft/conductor](https://github.com/microsoft/conductor):

```
ingest → baseline gate → plan (claude) → adversarial plan review (gpt) ⟲
→ human gate → [ implement (claude) → deterministic gate ⟲ fix
                 → adversarial chunk review (gpt) → commit ] per chunk
→ security review (claude) ∥ spec-compliance matrix (gpt)
→ harvest (self-improvement) → deep gate → human ship gate → push + PR
```

The engine is generic. Everything repo-specific — gate commands, context
docs, security invariants, harvest allowlist — lives in a committed
`.mill.toml` in each consuming repository (see `mill.toml.example`).

## Design rules

- **All control flow is deterministic.** Loop counters, gate results, and
  every git operation live in `mill_state.py`; LLM steps never decide when a
  loop ends and never run git. Bounded retries everywhere; exhaustion
  terminates with a resumable checkpoint instead of thrashing.
- **LLM output shapes can't kill a run.** Reviewers reply in free text
  ending with a JSON block; deterministic gates normalize it
  (rejection-biased when unparseable).
- **Cross-model adversarial review.** Claude implements; GPT (via the
  Copilot provider) reviews the plan, each chunk, and final spec compliance
  with a requirement-by-requirement matrix.
- **Reviewers are provably read-only** — staged-diff hash compared around
  every review; tampering is reverted and aborts the run.
- **Self-improvement.** Friction is journaled; a harvest step distills
  durable lessons into the repo's skills directory, committed inside the
  same PR, and read by every future run (and every other agent, via the
  cross-agent links millify creates).
- **Worktree isolation.** `mill.sh` runs conductor inside
  `.worktrees/mill-<id>`; the main checkout is never touched.
- **Humans gate the irreversible moments**: plan approval and ship.

## Install

```sh
curl -sSfL https://raw.githubusercontent.com/frostyard/mill/main/install.sh | sh
```

Prerequisites: [conductor](https://github.com/microsoft/conductor) with the
`claude-agent-sdk` extra (auth via `claude login`) and the Copilot provider
(auth via `gh auth login`):

```sh
curl -sSfL https://aka.ms/conductor/install.sh | sh
uv tool install --force 'conductor-cli[claude-agent-sdk] @ git+https://github.com/microsoft/conductor.git@v0.1.25'
```

(Do not install `conductor-cli` from PyPI — that's an unrelated package.)

## Set up a repository

In Claude Code, run the `millify` skill in the target repo — it inspects the
build system, generates `.mill.toml`, seeds the skills directory, and wires
the cross-agent surfaces (`CLAUDE.md`, `.github/copilot-instructions.md`,
`.agents`, `GEMINI.md` → all reading the canonical `AGENTS.md`). Or copy
`mill.toml.example` to `.mill.toml` and edit by hand.

## Run

```sh
mill 35                    # run issue #35, interactive gates
mill spec.md --auto        # unattended (auto-approves gates)
mill 35 --no-pr --no-deep  # local-only, fast gates
```

First run on a new repo: use interactive gates and `--no-pr`, and
sanity-check the plan at the approval gate.

Run state lives in `.mill/` inside the worktree (spec, plan, progress,
journal, final report). Resume a stopped run with `conductor resume` from
the worktree; the plan and completed chunks are preserved.
