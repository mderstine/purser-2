---
name: purser-plan
description: Decompose one or more specs into Beads work items.
---

# purser-plan

Use this skill when the user wants the Codex equivalent of `/purser-plan`.

Arguments: Optional spec ID; if omitted, plan the relevant unplanned specs.

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Decompose specs into Beads work items.

- If a spec ID is provided, run `uv run purser plan create <spec_id>`.
- Otherwise list specs, choose the relevant one, and run the planner.
- Report the created epic, feature, and task IDs.
