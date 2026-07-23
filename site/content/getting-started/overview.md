---
title: Overview
description: What the mill is, and why it exists.
group: Getting started
order: 1
---

Grain goes in, flour comes out, and the machinery doesn't improvise.

The mill is frostyard's spec-to-PR harness. It takes a complete
specification — a GitHub issue or a markdown file — and turns it into a
reviewed, gated, evidenced branch, using coding agents for the work and
deterministic scripts for everything that must not depend on a model's mood.

## The problem

Coding agents are genuinely good at writing software now, but using them is
still guesswork. You hand an agent a big piece of work and get back a big
pile of plausible changes — and you're the one holding the bag. Did it cover
the whole spec, or the parts it found interesting? Did the tests actually
run, or did it say they ran? Every answer costs a careful read of everything
it did, which was the work you were trying to delegate in the first place.

The fragility isn't in the models. It's in handing one model the job, the
grading of the job, and the decision about when to stop — all in one
context, with no adversary and no referee.

## What the mill does differently

The mill splits those roles apart:

- **Scripts referee.** Every loop, counter, gate, and git operation is
  deterministic code. If `make test` is red, no amount of eloquence ships
  the chunk.
- **A rival model grades.** claude implements; a different vendor's model —
  prompted to reject, not to assist — reviews the plan, every chunk, and
  finally walks the spec requirement by requirement with file:line evidence.
- **You decide the irreversible things.** The run pauses at exactly two
  moments: plan approval and ship. Everything between runs unattended in an
  isolated git worktree.
- **Every run makes the next one smarter.** Friction is journaled, distilled
  into written lessons, committed inside the same PR, and read by every
  future run.

## The result

You hand the mill a complete specification and get back either a branch
where every requirement is evidenced and every gate is green, or an honest,
early, bounded failure telling you exactly which assumption broke. Both
outcomes are cheap to act on. The mill spends tokens freely to verify, so
you don't spend attention to trust.

Start with [installation](/getting-started/installation), then take
[your first run](/getting-started/first-run).
