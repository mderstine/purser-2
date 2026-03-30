---
name: purser-build
description: Claim and build the next ready bead from the queue.
argument-hint: Optional bead ID or scope guardrails if you do not want the default next ready item.
agent: Purser Worker
tools: ['editFiles', 'runCommands', 'terminalLastCommand', 'changes', 'problems', 'search']
---
Claim and execute exactly one ready bead in this workspace.

Before you start, load [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md).

Execution policy:

- If a bead ID is provided, respect it. Otherwise run `bd ready` and pick the top safe ready bead.
- Claim the bead with `bd update <id> --claim` before starting work.
- Read the issue with `bd show <id>`, implement only that scope, run relevant quality gates, and close it with `bd close <id> --reason "<what changed>"`.
- If GitHub integration is enabled, check `purser gh status` at the start and sync changed work state back as needed.
- End with the claimed bead ID, what changed, and what tests or lint commands ran.
