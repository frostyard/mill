---
title: mill command
description: Driver flags and run mechanics.
group: Reference
order: 20
---

```sh
mill <issue#|spec-file> [--auto] [--web] [--no-pr] [--no-deep] [--fresh]
```

The argument is either a GitHub issue number (fetched with `gh` from the
current repository) or a path to a markdown spec file.

| Flag | Effect |
| --- | --- |
| `--auto` | Unattended: auto-approve both human gates. Escalations choose the safe option (a deadlocked plan aborts). |
| `--web` | Detach into the background with a live web dashboard — the pipeline as a real-time graph, streaming agent output, and in-browser human gates (`conductor gate respond` works too). |
| `--no-pr` | Never push or open a PR; the branch stays local regardless of the ship decision. |
| `--no-deep` | The final gate re-runs the fast chunk gates instead of `[gates].deep`. |
| `--fresh` | Discard an existing worktree and branch for this source and start over. |

## Where things live

| Path | Contents |
| --- | --- |
| `.worktrees/mill-<id>/` | The isolated worktree the run executes in. |
| `mill/<id>` | The branch chunks are committed to. |
| `.mill/` (inside the worktree) | Run state: spec, plan, progress, journal, objections, final report. Self-gitignored. |
| `/tmp/conductor/` | Event logs and checkpoints. |

## Resuming

A stopped or failed run resumes from its checkpoint — the plan and all
committed chunks are preserved:

```sh
cd .worktrees/mill-<id>
conductor resume ~/.local/share/frostyard-mill/mill.yaml
```

## Cleaning up

```sh
git worktree remove --force .worktrees/mill-<id>
git branch -D mill/<id>
```
