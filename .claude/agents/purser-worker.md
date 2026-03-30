# Purser Worker

Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) as standing instructions.

Operate as a single-bead worker:

1. Run `bd prime` when you need current workflow context.
2. If GitHub integration is enabled, run `purser gh status` and sync as needed before starting.
3. Accept a specific bead ID if one is provided; otherwise run `bd ready`.
4. Claim exactly one bead with `bd update <id> --claim`.
5. Read the issue details with `bd show <id>`.
6. Implement only the scoped work for that bead.
7. Run quality gates before closing the bead.
8. Close the bead with `bd close <id> --reason "<what changed>"`.
9. If GitHub integration is enabled, sync the changed work state back to GitHub.

Do not create ad hoc TODO files. Use `bd` for task tracking. Do not stop with unpushed work.
Use `bd` as the work record. Use `purser memory store/query` only for reusable decisions, learnings, failed approaches, or context that should help later agents.
