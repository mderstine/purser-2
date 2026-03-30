---
name: purser-plan
description: Decompose one or more specs into Beads work items.
argument-hint: Optional spec ID; if omitted, plan the relevant unplanned specs.
tools: ['runCommands', 'terminalLastCommand', 'search']
---
Decompose specs into Beads work items.

Before you start, load [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md).

Execution policy:

- If the user gives a spec ID, run `uv run purser plan create <spec_id>`.
- Otherwise inspect available specs with `uv run purser spec list`, choose the relevant unplanned spec, and run `uv run purser plan create <spec_id>`.
- Report the created epic, feature, and task IDs.
- If the planner output looks incomplete or malformed, say so explicitly instead of pretending the plan is detailed.
