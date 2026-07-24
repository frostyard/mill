---
name: drive-mill
description: Operate the frostyard mill (spec→PR harness) to take a GitHub issue or spec through to a branch — decompose an umbrella issue into phases, harden each spec, launch runs, read the gate signals, and handle clarify parks, deadlocks, and concurrency safely. Use when the user asks to run/drive the mill, take an issue through the mill, run a phase, or kick off a mill run.
---

# Drive the mill

This is the operator playbook for running the mill against a repository's
issues. The mill itself is deterministic; *driving* it well is a discipline.
The failure mode is thrash — aborted launches, re-derived context, wasted
tokens — and almost every rule here exists to prevent one specific kind.

Prerequisite: the repo has a `.mill.toml` (run the `millify` skill first if
not). Runs use the **installed** engine at `~/.local/share/frostyard-mill`,
not any repo clone — see [Engine drift](#engine-drift-hazard).

## 0. The shape of a good run

`spec-prep <issue>` → hardened spec → `mill <issue>` → spec gate passes on
the first try → plan → your approval → chunk loop → final reviews → branch.
When a run parks or deadlocks, it is almost always the **spec's** fault, not
the pipeline's. Fix the spec, not the run.

## 1. Decompose an umbrella issue into phases

A large feature issue is not one run. Break it into phases small enough to
converge — each a **single run of roughly ≤12 chunks**, in dependency order,
each landing on `main` before the next starts. A phase that honestly
estimates much beyond a dozen chunks should be split again.

Phases are sequential for a reason: **later-phase specs drift from
merged-earlier-phase reality.** You cannot fully harden phase N+1 until phase
N is merged, because N+1 references code N ships. Re-grounding is irreducible
per-phase work; do not try to pre-harden the whole umbrella up front.

## 2. Re-ground each phase before launching it

Before every phase, verify its spec against the **currently merged** code —
not the code as it was when the issue was written:

- `git fetch && git checkout main && git pull` so you compare against reality.
- Read the issue body. For every concrete claim it makes about the code —
  a function, type, capability, flag, file — confirm it actually exists now
  (grep/read it). Prior phases change these.
- Fix stale references at the source before running. This catches drift that
  would otherwise surface as a spec-gate clarify on round one.

## 3. Harden the spec with spec-prep (don't hand-edit in a loop)

If the spec is underspecified or you expect defects, run the pre-flight
**before** the mill:

```sh
spec-prep <issue> --web
```

It reviews against source truth, then a hardener resolves blocking/high
findings and loops until none remain (medium/low are recorded, not blocking).
It emits `.mill-prep/spec.hardened.md`. Genuine *product* decisions it can't
settle from code (expose a UI or not; add fixtures or test synthetically) are
logged to `.mill-prep/spec_decisions.json`; to decide them yourself first,
write authoritative answers to `.mill-prep/spec_answers.md` and rerun.

Feed the result to the mill: `mill .mill-prep/spec.hardened.md`. If the issue
body already holds the hardened content, running `mill <issue>` directly is
fine and gives a nicer issue-linked PR.

**Do not** hand-edit the issue, rerun, hit the next clarify, hand-edit again,
four times over. That is exactly the thrash spec-prep exists to replace: an
adversarial source-reader can always name one more edge case, so chasing
"zero findings" by hand is an asymptote. Harden once, up front.

## 4. Launch

```sh
mill <issue> --auto --web --no-pr --model=opus
```

- `--auto` — unattended; auto-approves the human gates (safe options on
  escalation).
- `--web` — background run with the live dashboard (note its port).
- `--no-pr` — keep the branch local; the user merges (see §8).
- `--model=opus` — use for reasoning-heavy phases (parsers, contract tests,
  capability tables). Mechanical phases are fine on the default sonnet.

Drop `--auto` for a first run on a new repo, so you can eyeball the plan.

## 5. Read the signals

Watch `.worktrees/mill-<id>/.mill/journal.jsonl` and the dashboard:

- **Spec gate** — `spec_review verdict: sound` → planning (the goal). A
  `clarify` park means the spec still has defects (see §6). After a proper
  spec-prep pass this should pass first try.
- **Plan size** — a plan of ≫12 chunks means the phase is too big; stop and
  split it.
- **Plan-review trajectory** — the escalation reports whether objections are
  *converging* (fix those few points), *repeating* (one reviewer/planner
  disagreement — decide it), or *finding new sections each round* (spec too
  large — decompose).
- **Chunk loop** — implement → gates → review → commit, bounded. The hardest
  class is **contract-test and parser chunks**: budget a single opus resume
  for them.

## 6. Handle a clarify park

Read `.mill/spec_findings.json`. Classify each finding:

- **Source-groundable** (wrong reference, a schema that should follow an
  existing type, a degraded-mode behavior the code already implies): resolve
  it yourself against the code and fix the spec — this is what spec-prep's
  hardener automates.
- **Genuine product decision** (scope, UI-or-not, fixtures-or-synthetic):
  surface it to the human with a recommendation grounded in precedent. Do
  not invent the answer.

Prefer **fixing the spec at its source and rerunning** (or a spec-prep pass)
over "proceed anyway" — proceeding bakes the defect into the plan. If you
resolve findings by hand, verify each edit actually landed (issue bodies get
reflowed; a blind string-replace can silently no-op), then confirm with a
grep before relaunching.

## 7. Handle a deadlock

A chunk that exhausts its bounded retries stops with a resumable checkpoint
and a failure-harvest. The reliable recovery: read what harvest learned,
resume carrying the explicit objections, and — for the hard classes — bump
to opus. Do not paper over a red gate; a script decides pass/fail, and piping
a gate through `tail` to swallow its exit code is the exact sin the reviewers
flag.

## 8. Finish

With `--no-pr` the branch is local. Verify it (`git log`, tree clean), report
what shipped (chunks, files, security + compliance verdicts), and let the
**user** publish/merge — that is an outward action that is theirs to take.
When they ask you to publish, run the publish step from the worktree:

```sh
cd .worktrees/mill-<id> && python3 ~/.local/share/frostyard-mill/mill_state.py publish
```

The PR title is the spec's title verbatim, so ensure the spec title is a
valid conventional-commit subject (e.g. `feat: …`), or the squash-merge trips
commit-lint.

## Concurrency safety (do not break other runs)

The user may run **several mills at once, across different projects**.

- **Never** `conductor stop --all` or `pkill -f conductor` — it is
  cross-project and kills their other runs. Stop only *your* run, by its
  dashboard **port** (`conductor gate respond --port <p> --choice abort` to
  clear a parked gate) or its PID.
- Clean only the worktree you launched (`.worktrees/mill-<id>`), never a
  blanket sweep.
- The driver refuses a second run in the same worktree; honor that rather
  than forcing `--fresh` over a live run.

## Engine drift hazard

Runs execute `~/.local/share/frostyard-mill/mill_state.py` (and `mill.yaml`),
re-loaded fresh on every script step — **not** any repo clone. So:

- If a run misbehaves in a way the repo source doesn't explain, diff the
  installed engine against the repo; they may have drifted.
- After editing the engine, sync the installed copy (`git pull` in it, or
  reinstall) before relying on the change.
- **Do not edit the shared engine while other runs are in flight** — every
  script step of every live run picks up your change mid-run. Additive
  changes are usually safe; behavioral ones are not. Wait for the batch to
  drain, or flag it to the user first.
