---
name: purser-add-spec
description: Create a new structured Purser spec from a feature description.
argument-hint: Provide the feature description or requirement to turn into a spec.
tools: ['runCommands', 'terminalLastCommand', 'search']
---
Create a new Purser spec from the user-provided description.

Before you start, load [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md).

Execution policy:

- Run `uv run purser spec add "<description>"` using the user-provided requirement text.
- If the requirement text is in a file, inspect it first, then feed the relevant description into `purser spec add`.
- Report the created spec ID, title, and file path.
- Offer the follow-up command to inspect or plan it next.
