---
name: purser-build-all
description: Execute a Purser Ralph loop over all ready beads.
---

# purser-build-all

Use this skill when the user wants the Codex equivalent of `/purser-build-all`.

Arguments: Optional scope guardrails, for example "stop after frontend work" or "only docs and tests".

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Run a Purser Ralph loop in this workspace.

Execution policy:

- Work only from the Beads queue.
- If GitHub integration is enabled, check `purser gh status` at the start and sync before and after the batch as needed.
- Repeatedly run `bd ready`, claim one bead, complete it, lint/test, close it, and move to the next ready bead.
- Keep going until no safe ready beads remain.
- Use `bd` as the authoritative work record; use `purser memory` only for reusable context and learnings worth carrying across sessions.
- If you stop because the queue is blocked, explain exactly which bead blocked progress and what follow-up is needed.
- End with a compact report of:
  - completed beads
  - blocked or deferred beads
  - discoveries filed
  - commands/tests run
