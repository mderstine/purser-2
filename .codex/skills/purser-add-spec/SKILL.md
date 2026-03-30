---
name: purser-add-spec
description: Create a new structured Purser spec from a feature description.
---

# purser-add-spec

Use this skill when the user wants the Codex equivalent of `/purser-add-spec`.

Arguments: Provide the feature description or requirement to turn into a spec.

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Create a structured Purser spec from a requirement description.

- Run `uv run purser spec add "<description>"`.
- Report the created spec ID, title, and file path.
- Offer the follow-up inspection or planning command.
