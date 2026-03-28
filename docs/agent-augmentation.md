# Purser Agent Augmentation

Purser is the workflow layer. The host agent stays responsible for coding, terminal
interaction, and applying changes. Purser adds:

- specs via `purser spec ...`
- decomposition via `purser plan ...`
- queueing and state via `bd`
- memory via `purser memory ...`
- quality checks via `purser lint`

## Work Record vs Memory

Purser uses two different persistence layers for different jobs:

- Beads is the authoritative work record. Use it for decomposition, dependencies, status, discoveries, and completion.
- DuckDB memory is the reusable context layer. Use `purser memory store/query` for decisions, learnings, failed approaches, debugging context, and other information that should help future agents work with smaller context windows.

Practical rule:

- If it changes the task graph or project state, put it in Beads.
- If it captures reusable understanding, put it in DuckDB memory.

## GitHub Sync

When Purser GitHub integration is enabled, agents are expected to keep GitHub in sync
with the Beads work graph.

Use:

- `purser gh status` to inspect configuration and current sync state
- `purser gh sync` for normal bidirectional synchronization
- `purser gh push` when local Beads changes are authoritative and should be published
- `purser gh pull` when remote GitHub changes should be imported locally

Operational rule:

- Check GitHub sync state at session start.
- Sync before a larger autonomous batch if local and remote may have diverged.
- Sync again after changing work state so GitHub Issues and Project items stay current.

## Ralph Loop

In Purser terms, a Ralph loop means:

1. Inspect the ready queue with `bd ready`
2. Claim one bead with `bd update <id> --claim`
3. Implement the bead
4. Run quality gates
5. Close the bead with `bd close <id> --reason "..."`
6. Repeat until no safe ready beads remain

Memory is not a mandatory loop step. Store memory only when it would materially help a later bead or later session.
When GitHub integration is enabled, sync is part of the loop boundary even though it does not replace Beads as the source of truth.

## VS Code

VS Code now supports:

- workspace `AGENTS.md`
- custom agents in `.github/agents`
- slash-command prompt files in `.github/prompts`
- agent hooks in `.github/hooks` or agent frontmatter
- background agent sessions for longer-running autonomous work

This repository ships a VS Code implementation:

- `.github/agents/purser-worker.agent.md`
- `.github/agents/purser-build-all.agent.md`
- `.github/prompts/purser-build-all.prompt.md`
- `scripts/vscode/purser_stop_hook.py`
- `scripts/vscode/purser_post_tool_hook.py`

Recommended settings to enable the full workflow:

```json
{
  "chat.useAgentsMdFile": true,
  "chat.useCustomAgentHooks": true
}
```

Use `/purser-build-all` from chat or a background agent session when you want the
agent to keep draining the ready queue.

While looping:

- Keep work state in `bd`
- Store DuckDB memory only for non-obvious decisions, learnings, blockers, failed attempts, or context that should survive a narrower future session
- Check `purser gh status` at the start of a session when GitHub integration is enabled
- Run `purser gh sync` before and after a larger autonomous batch so GitHub stays aligned with Beads

## Codex CLI

Codex does not use VS Code prompt files or hooks, but it can follow the exact same
workflow from `AGENTS.md` and terminal commands:

1. Run `bd prime`
2. Run `bd ready`
3. Claim one bead
4. Implement it
5. Run `purser lint` and relevant tests
6. Close the bead
7. Continue with the next ready bead

The loop is procedural rather than hook-driven, but the behavior is the same.

Apply the same memory rule: Beads for work state, DuckDB for reusable context.
Apply the same GitHub rule: if the repo is configured for GitHub sync, use `purser gh ...` as part of the normal session workflow.

## Claude Code

Claude Code can use the same `AGENTS.md` instructions and the same `bd`/`purser`
commands. If you want persona-level reuse, mirror the VS Code agents into
`.claude/agents`, but the workflow does not depend on that. The key idea is the same:
Purser owns project state, while Claude owns execution inside the current session.

## Design Boundary

Purser should stay generic by separating:

- workflow state and commands, which belong in Purser
- host-specific orchestration, which belongs in VS Code customizations or tool docs

That keeps the framework portable across VS Code, Codex, Claude, and other agent
hosts without making Purser depend on any single vendor UX.
