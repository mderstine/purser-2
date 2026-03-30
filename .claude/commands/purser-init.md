Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) before you start.

Arguments: Optional flags or intent, for example check-only, force re-init, or with GitHub setup.

Initialize Purser in the current repository or report setup status.

- Use `uv run purser init` for normal setup.
- Use `uv run purser init --check` for status-only requests.
- Use `uv run purser init --with-github` plus explicit `--repo`/`--project` when the user wants GitHub setup too.
- Report the resulting local and GitHub status clearly.
