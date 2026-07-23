---
title: How it works
description: The pipeline, stage by stage.
group: Concepts
order: 5
---

![The mill pipeline: ingest and baseline gate, then plan with adversarial
cross-model review and a human approval gate; then per-chunk implement,
quality gates, adversarial review, and commit, with bounded fix and revise
loops; then parallel security and spec-compliance reviews, harvest, deep
gate, human ship gate, and PR.](/flow.svg)

## Ingest and baseline

A script fetches the spec (a GitHub issue via `gh`, or a file) and records
the base commit. The repository's quality gates then run once before any
work starts — if the tree is already red, the run ends immediately, so every
later failure is attributable to the mill.

## Spec review, before anything else

A run's biggest risk is a spec that can't be implemented as written. Before
a token is spent planning, a rival model validates the specification itself
against source truth: does it assume flags, files, or behaviors the code
doesn't have? Does it contradict itself — especially universal invariants
("every", "always", "never") that current code doesn't satisfy and that lack
a transition rule? Is it ambiguous in ways that change the work? Is it small
enough to converge (roughly a dozen chunks)? Findings escalate to a human
immediately; in `--auto` runs they abort. Fix the spec at its source and
rerun — that's cheaper than discovering the same defects through six rounds
of plan review.

## Plan, adversarially reviewed

claude reads the spec, the repository's context docs, and every learned
skill, then writes a chunked plan: ordered, independently implementable
chunks with concrete acceptance criteria. A rival model walks the spec
section by section trying to reject the plan — unmapped requirements,
invariant violations, unreviewable chunks. Up to three revision rounds; a
deadlock escalates to a human rather than dead-ending, because repeated
rejection usually means the spec is ambiguous.

You approve the plan before implementation spends a token.

## The chunk loop

For each chunk, in order: claude implements exactly one chunk; the
repository's gates run (a red gate loops to a fix step, at most three
attempts); the staged diff goes to the rival reviewer against the chunk's
acceptance criteria (at most two revision rounds); a script commits and
advances the cursor. Every loop is bounded and every exit is deterministic.
Exhausting a bound ends the run as failed, with a resumable checkpoint —
after a failure-harvest step distills what the failed run learned (see
[self-improvement](/concepts/self-improvement)).

## Final reviews

Two reviews run in parallel over the whole branch: a security review against
the repository's declared invariants, and a spec-compliance audit that
produces a requirement-by-requirement matrix — met, unmet, or deferred, each
with file:line evidence. Any unmet requirement fails the run.

## Harvest

The run's friction — failed gates, objections, revision rounds — has been
journaled throughout. A harvest step distills at most three durable lessons
into the repository's skills directory, where every future run (and every
other agent, via the cross-agent links) reads them. A deterministic gate
reverts anything harvest touches outside its allowlist. See
[self-improvement](/concepts/self-improvement).

## Deep gate and ship

The heavyweight gate — typically the containerized test suite — runs last,
covering everything including the harvest commit. Then the second human
gate: read the final report, decide whether it ships. Publishing pushes the
branch and opens a PR whose body carries the plan and the compliance matrix.
