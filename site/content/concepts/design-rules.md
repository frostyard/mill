---
title: Design rules
description: The invariants that make mill runs trustworthy.
group: Concepts
order: 7
---

Each rule here exists because its absence produced a concrete failure —
either in the mill's own shakedown runs or in ordinary agent use.

## Validate the spec before trusting it

Every deadlock in the mill's shakedown traced to a spec defect — never to
the pipeline. So the spec is verified before anything else: grounded in
source truth, internally consistent, unambiguous, and sized to converge.
Universal invariants over existing code must carry transition rules, or
they are unsatisfiable incrementally and two honest models will spend six
rounds proving it.

What blocks is severity, not count. An adversarial reader of a real codebase
can almost always name one more edge case, so "zero findings" is an asymptote
— demanding it just trades six rounds of plan review for six of spec review.
The bar is *no blocking or high-severity defect*; medium and low findings are
recorded as accepted interpretations and carried into planning, where three
downstream review gates still cover them. The optional
[`spec-prep`](/concepts/spec-prep) pre-flight applies exactly this bar to
harden a spec to a millable state before a run starts.

## Scripts own control flow

Loop counters, gate results, and every git operation live in
`mill_state.py`. A model never decides whether tests passed, when to stop
retrying, or what gets committed. Bounded retries everywhere: three plan
rounds, three gate attempts per chunk, two review rounds per chunk.
Exhaustion terminates the run with a reason and a checkpoint instead of
thrashing.

## Model output shapes can't kill a run

Reviewers reply in free text ending with a JSON block. Deterministic gates
normalize whatever comes back — fenced blocks, dict-wrapped verdicts,
keyword fallback — and treat anything unparseable as a rejection. This rule
was learned the expensive way: an early run died mid-flight because a
reviewer returned `verdict` as a nested object and the orchestrator treated
the type mismatch as fatal.

## Reviewers are provably read-only

"Reviewers must not modify files" is only a prompt-level promise, so the
mill doesn't rely on it: a script snapshots the staged diff hash before each
review and compares after. Any drift is reverted and aborts the run.

## The diff is untrusted data

Reviewed diffs and fetched specs are data, not instructions. Reviewer
prompts state this explicitly, and the read-only check above backs it with
enforcement.

## Worktree isolation

The driver runs conductor inside `.worktrees/mill-<id>` on a dedicated
branch. Your checkout is never touched; a failed run is
`git worktree remove --force` away from gone.

## Humans gate the irreversible moments

Plan approval — the cheap moment to redirect, before implementation spends
tokens — and ship, before anything leaves the machine. `--auto` skips both
for trusted repositories; `--no-pr` guarantees nothing is pushed regardless.

## Cross-model review

The model that writes the code never grades its own homework. Review runs
on a different vendor's model with different blind spots, prompted to
reject. Agreement between rivals is worth more than confidence from either.
