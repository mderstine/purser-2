# Purser Build All

Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) as standing instructions.

You are running a Ralph loop over the ready bead queue.

Loop contract:

1. If GitHub integration is enabled, run `purser gh status` and sync before starting the batch if needed.
2. Run `bd ready` and pick the highest-priority ready bead.
3. Claim it with `bd update <id> --claim`.
4. Read it with `bd show <id>`.
5. Implement the bead completely, staying within scope.
6. Run relevant quality gates.
7. Close it with `bd close <id> --reason "<what changed>"`.
8. If GitHub integration is enabled, sync the changed work state back to GitHub.
9. Repeat until `bd ready` is empty or the remaining work is blocked, unsafe, or requires a human decision.

Rules:

- Work through beads sequentially, one claimed bead at a time.
- If you discover unrelated work, file a new bead instead of expanding scope.
- Summarize completed, blocked, and newly discovered work before finishing.
- Do not stop early just because one bead completed; continue until the queue is exhausted or there is a clear blocker.
- Keep work state in `bd`. Store DuckDB memory only for reusable decisions, learnings, failed approaches, or context that should help future narrower sessions.
