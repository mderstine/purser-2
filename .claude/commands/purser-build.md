Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) before you start.

Arguments: Optional bead ID or scope guardrails if you do not want the default next ready item.

Claim and execute exactly one ready bead.

- Run `bd ready --limit 1` unless the user names a specific bead.
- Claim the bead with `bd update <id> --claim`, inspect it with `bd show <id>`, implement only that scope, run relevant quality gates, and close it.
- End with the bead ID, what changed, and the validation commands that ran.
