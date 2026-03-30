---
name: purser-init
description: Initialize Purser in the current repository and report setup status.
---

# purser-init

Use this skill when the user wants the Codex equivalent of `/purser-init`.

Arguments: Optional flags or intent, for example check-only, force re-init, or with GitHub setup.

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Initialize Purser in the current repository or report status.

- Use `uv run purser init` for setup.
- Use `uv run purser init --check` for status-only requests.
- Use `uv run purser init --with-github` plus `--repo`/`--project` when GitHub setup is desired.
- Report local and GitHub setup state clearly.
