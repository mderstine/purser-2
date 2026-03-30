Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) before you start.

Arguments: Provide the feature description or requirement to turn into a spec.

Create a structured Purser spec from the user-provided requirement text.

- Run `uv run purser spec add "<description>"`.
- Report the created spec ID, title, and file path.
- Offer to inspect it with `uv run purser spec show <id>` or plan it with `uv run purser plan create <id>`.
