Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) before you start.

Arguments: Optional spec ID; if omitted, plan the relevant unplanned specs.

Decompose one or more specs into Beads work items.

- If the user provides a spec ID, run `uv run purser plan create <spec_id>`.
- Otherwise list specs with `uv run purser spec list`, choose the relevant one, and run the planner.
- Report the created epic, feature, and task IDs.
