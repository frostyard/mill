---
title: Hardening a spec first
description: The optional pre-flight that makes a spec millable before a run spends a token.
group: Concepts
order: 6
---

The mill validates the spec at the start of every run. A spec with real
defects fails that gate — and because the reviewer reads *source truth*, a
large spec can surface a *different* defect on each pass: you fix one, rerun,
and the next round finds the next. Fixing at the source and rerunning the
whole pipeline each time is correct but slow, and it drags a human through
one decision at a time.

`spec-prep` moves that hardening into its own cheap loop that runs to
convergence *before* the implementation mill starts. It has no worktree and
no baseline — it only reads the code and rewrites its own copy of the spec —
so looping is fast, and the mill it feeds sails straight through the spec
gate it would otherwise park at.

## The loop

![The spec-prep pre-flight loop: a spec is reviewed against source truth,
then a severity gate either passes it through as a hardened spec into the
mill (no blocking findings), sends it to a Claude hardener that resolves
blocking findings and loops back to review, or stalls when the round budget
is spent and a decision is needed.](/spec-prep.svg)

A rival model reviews the spec against the code, exactly as the mill's own
spec gate does. Then a **hardener** — a strong model with repository access —
rewrites the spec to resolve each finding, grounded in the actual files and
existing precedent, and the loop reviews again. It repeats until the review
comes back clean or a round budget is spent.

## Severity decides what blocks

The key move — and the reason the pre-flight converges where a bare rerun
loop doesn't — is that not every finding blocks:

- **blocking / high** findings must be resolved. A false claim about the
  code, a genuine contradiction, an ambiguity that changes the shape of the
  work — the spec can't be implemented correctly until these are fixed.
- **medium / low** findings are recorded as *accepted interpretations* and
  carried into planning, not treated as blockers.

Demanding *zero* findings from an adversarial reader of a real codebase is an
asymptote it never quite reaches — there is almost always one more
serve-time edge case to name. And three more review gates sit downstream in
the mill (plan review, per-chunk review, final compliance). So the pre-flight
converges on "no blocking defects remain," records the rest, and lets the
pipeline's later gates catch residual depth.

## The hardener resolves; it doesn't guess

For a finding that source truth settles — a wrong file reference, a schema
that should follow an existing type — the hardener corrects the spec and
cites the real code. For a genuine *product* decision that the code can't
settle — expose a UI or stop at the API, add fixtures or test synthetically —
it picks the most conservative, smallest-scope reading, writes the spec to
that reading so it is unambiguous, and records the decision in
`.mill-prep/spec_decisions.json` for a human to review or override.

To decide those forks yourself up front, put authoritative answers in
`.mill-prep/spec_answers.md` before running; the hardener honors them exactly
rather than choosing. Either way, the finished spec carries a **Spec-prep
record** — every interpretation and decision made — so nothing is silently
chosen.

## Running it

```sh
spec-prep 58                              # harden issue #58
spec-prep 58 --web                        # with the live dashboard
mill .mill-prep/spec.hardened.md --no-pr  # then implement the hardened spec
```

| Flag | Effect |
| --- | --- |
| `--web` | Detach into the background with the live web dashboard. |
| `--fresh` | Discard existing `.mill-prep` state and start over. |
| `--dest=PATH` | Where to write the hardened spec (default `.mill-prep/spec.hardened.md`). |

The output is a spec file — with a title header, so a file-sourced mill run
derives a good PR title — that the mill consumes directly. If the source
issue was already sound, `spec-prep` finalizes on the first review with
nothing to change; if it can't converge within the round budget, it stalls
with the unresolved findings, which usually means a product decision is
waiting for you in `spec_answers.md`.

State lives in its own `.mill-prep/` directory (self-gitignored), so
`spec-prep` never collides with an implementation run's `.mill/` in the same
checkout. See [running concurrently](/reference/concurrency).
