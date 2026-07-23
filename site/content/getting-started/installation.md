---
title: Installation
description: Install the mill engine and its prerequisites.
group: Getting started
order: 2
---

## Prerequisites

The mill orchestrates its agents with
[conductor](https://github.com/microsoft/conductor) and needs two providers:
the claude-agent-sdk provider (implementation and security review) and the
copilot provider (adversarial cross-model review).

```sh
curl -sSfL https://aka.ms/conductor/install.sh | sh
uv tool install --force 'conductor-cli[claude-agent-sdk] @ git+https://github.com/microsoft/conductor.git@v0.1.25'
```

Do not install `conductor-cli` from PyPI — that is an unrelated package that
shadows the real conductor.

Authentication is whatever you already have: the claude-agent-sdk provider
uses your `claude login`, the copilot provider uses your `gh auth login`.
Verify both with:

```sh
conductor doctor
```

## Install the mill

```sh
curl -sSfL https://raw.githubusercontent.com/frostyard/mill/main/install.sh | sh
```

This clones the engine to `~/.local/share/frostyard-mill`, puts a `mill`
command on your path, and — if you use Claude Code — links the `millify`
onboarding skill into `~/.claude/skills`. Run the same command again any
time to update.

## Set up a repository

Each consuming repository carries one committed file, `.mill.toml`, naming
its gates, context docs, security invariants, and skills directory. Two ways
to create it:

- In Claude Code, run the `millify` skill from the repo root. It inspects
  the build system, generates `.mill.toml`, seeds the skills directory, and
  wires the cross-agent surfaces (`CLAUDE.md`, `GEMINI.md`,
  `.github/copilot-instructions.md`, `.agents` — all reading the canonical
  `AGENTS.md`).
- Or copy `mill.toml.example` from the engine repo and edit by hand. The
  [configuration reference](/reference/mill-toml) covers every key.
