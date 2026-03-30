---
name: purser-build
description: Claim and build the next ready bead from the queue.
---

# purser-build

Use this skill when the user wants the Codex equivalent of `/purser-build`.

Arguments: Optional bead ID or scope guardrails if you do not want the default next ready item.

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Claim and execute exactly one ready bead.

- Run `bd ready --limit 1` unless the user names a specific bead.
- Claim the bead, inspect it, implement only that scope, run relevant validation, and close it.
- Report the bead ID and what changed.
