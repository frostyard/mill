---
title: Self-improvement
description: How runs turn friction into policy.
group: Concepts
order: 7
---

Mistakes should be made once, then become policy. The mill closes that loop
mechanically.

## Journal

As a run proceeds, every piece of friction is appended to
`.mill/journal.jsonl`: failed gates with their logs, reviewer objections,
plan and chunk revision rounds, chunk completions.

## Harvest

After the final reviews pass, a harvest step reads the journal and distills
at most three lessons that clear a durability bar: would this have prevented
friction in this run, and would it plausibly apply to a different spec?
Task-specific facts and anything already stated in the context docs don't
qualify.

Each lesson becomes a small file in the repository's skills directory —
when it applies, what to do, and which run taught it. A deterministic gate
enforces that harvest touches nothing outside its allowlist, then commits
the lessons inside the same PR as the code, so a human reviews what was
learned alongside what was built.

## Skills feed every future run

The planner, the implementer, and every reviewer read the skills directory
before working. A lesson harvested from run n changes behavior in run n+1 —
this was demonstrated in the mill's own shakedown: a chunk that deadlocked
in one run (a reviewer demanding a gitignored generated file appear in the
diff) sailed through the next, because the seeded skill taught the reviewer
to verify generated files on disk instead.

## Every agent benefits, not just the mill

The `millify` skill wires cross-agent surfaces in each repository:
`CLAUDE.md`, `GEMINI.md`, and `.github/copilot-instructions.md` are
symlinks to the canonical `AGENTS.md`, and `.agents` links to the directory
holding the skills. One source of truth — whatever tool reads the repo,
lessons the mill learned apply.
