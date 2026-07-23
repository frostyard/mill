---
title: Running concurrently
description: What the mill isolates, what it doesn't, and how to run several at once.
group: Reference
order: 22
---

Several mill runs can execute at the same time — one per phase issue, or one
per project. The dashboard port auto-selects, so runs never collide there.
But "isolated" has a precise boundary, and crossing it causes flaky gates.

## What the mill isolates

- **Worktree and branch** — each run works in `.worktrees/mill-<id>` on
  `mill/<id>`. Different ids never share files.
- **Run state** — `.mill/` lives inside each worktree.
- **Dashboard port** — auto-selected per run.
- **Event logs and checkpoints** — timestamp-stamped under `/tmp/conductor/`.
- **Git** — the shared object store is concurrency-safe; each worktree has
  its own index.

The driver also **refuses to launch a second run against the same
worktree** (same id, same repo): a live conductor already using that
worktree as its cwd blocks the launch, so you can't corrupt an in-flight
run — not even with `--fresh`.

## What the mill does NOT isolate

The mill isolates the filesystem and git. It does **not** give each run its
own network namespace or host resources. Anything your gates or dev servers
bind on the host is shared across concurrent runs:

- a fixed TCP port (a dev server on `:9999`, a test that binds `:8080`)
- a fixed Unix socket path
- a shared database, cache, or lockfile at a fixed path
- a fixed temp directory

Two runs whose gates touch the same one will contend or fail — and it will
look like a flaky gate, not a contention bug.

## Making a repo parallel-safe

Concurrency safety lives in the repo's own tests and dev servers, not in the
mill. To run several mills against one project at once:

- Bind ephemeral ports (port `0`, or Go's `httptest.NewServer`), never fixed
  ones, in tests.
- Put sockets, databases, and temp files under a per-test temp dir
  (`t.TempDir()` and equivalents), never a fixed path.
- If a dev server must run during a gate, give it a per-run port from the
  environment rather than a hard-coded one.

A quick audit: grep the test suite for fixed ports and fixed socket/temp
paths. If it only uses ephemeral ports and per-test temp dirs, concurrent
runs are safe.

## Shared-but-safe resources

Concurrent deep gates share the build image and the Go/lint cache volumes.
These are concurrency-safe, so runs won't corrupt each other — but they do
contend, so N parallel runs is not N× throughput. Both providers also draw
on the same rate limits.
