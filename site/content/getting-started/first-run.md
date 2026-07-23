---
title: Your first run
description: A supervised first pass through the mill.
group: Getting started
order: 3
---

From the root of a repository with a `.mill.toml`:

```sh
mill 35 --no-pr
```

That takes issue 35 through the full pipeline with interactive gates and
guarantees nothing leaves your machine. For a first run on a new repository,
this is the shape to use: you want to see the plan before tokens are spent
implementing it, and you want to read the final report before anything is
pushed.

## What you'll see

The mill creates an isolated worktree at `.worktrees/mill-issue-35` on
branch `mill/issue-35` and runs there — your checkout is never touched. It
fetches the spec, proves the tree is green, and asks claude for a chunked
plan, which a rival model then tries to reject. When the plan survives
review, the run pauses at the first human gate: read `.mill/plan.md` and
decide.

After approval the chunk loop runs unattended: implement, gate, review,
commit, repeat. See [the live dashboard](#the-live-dashboard) below for the
best way to watch.

The run ends at the second human gate with a final report in
`.mill/final_report.md` — a security verdict and a requirement-by-requirement
compliance matrix. Since you passed `--no-pr`, the branch stays local
regardless of what you choose.

## The live dashboard

Add `--web` and the run detaches into the background with a local web
dashboard:

```sh
mill 35 --no-pr --web
```

```
Dashboard: http://127.0.0.1:41581
```

The dashboard shows the whole pipeline as a live graph — every agent, gate,
and loop, lighting up as the run moves — with streaming output from the
agent that's currently working. Human gates park there too: read the plan or
the final report, then answer in the browser, or from any shell:

```sh
conductor gate respond --port 41581 --choice proceed
```

This is the shape to use for long runs: close the laptop lid metaphorically,
keep the tab open literally.

## When something stops

Bounded loops mean runs stop instead of thrashing. A chunk that can't pass
its gates after three attempts, or a plan that can't survive three review
rounds, ends the run with a clear reason and a resumable checkpoint:

```sh
cd .worktrees/mill-issue-35
conductor resume ~/.local/share/frostyard-mill/mill.yaml
```

The plan and every committed chunk are preserved; only the remaining work
runs.

## Unattended runs

Once you trust a repository's gates:

```sh
mill spec.md --auto        # auto-approves both human gates
mill 35 --auto --no-deep   # fast gates instead of the deep suite
```

`--auto` chooses the safe option wherever a decision would have escalated to
you — a plan that deadlocks in review aborts rather than proceeding.
