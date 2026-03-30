---
name: purser-init
description: Initialize Purser in the current repository and report setup status.
argument-hint: Optional flags or intent, for example check-only, force re-init, or with GitHub setup.
tools: ['runCommands', 'terminalLastCommand']
---
Initialize Purser in this repository or report its current setup status.

Before you start, load [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md).

Execution policy:

- Use `uv run purser init` for normal setup.
- Use `uv run purser init --check` when the user wants status without modifying anything.
- Use `uv run purser init --force` only when the user explicitly asks to reinitialize.
- If the user wants GitHub coordination during setup, use `uv run purser init --with-github` plus `--repo` and `--project` when available.
- Report memory DB, specs directory, formulas directory, Beads status, and GitHub status.
