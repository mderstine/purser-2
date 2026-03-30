# Purser

Purser is a framework for turning specs into executable work queues and then
orchestrating implementation through Beads, persistent memory, and agent-friendly
CLI commands.

The framework is intentionally split into two layers:

- Purser owns workflow state: specs, plans, memory, linting, and Beads integration.
- The host tool owns execution: VS Code agents, Codex CLI, Claude Code, or another LLM tool.

That separation keeps Purser portable across multiple agent environments instead of
binding the framework to one model vendor or one editor.

## Core Concepts

- `purser spec ...`: intake and manage specs
- `purser plan ...`: decompose specs into epics, features, and tasks
- `bd ...`: queue, claim, and close work
- `purser memory ...`: persist reusable decisions, learnings, and session context between sessions
- `purser lint`: run code-quality checks
- `purser gh ...`: sync Beads with GitHub Issues and Projects when GitHub integration is enabled

## Setup

Initialize a repository locally:

```bash
uv run purser init
uv run purser init --check
```

That local setup creates and verifies:

- `specs/`
- `formulas/`
- `.purser/memory.duckdb`
- local Beads state via `bd init`

If you also want GitHub coordination, either configure it during init:

```bash
uv run purser init --with-github --repo owner/repo --project "Roadmap"
```

or attach it afterward:

```bash
uv run purser gh attach --repo owner/repo --project "Roadmap"
uv run purser gh sync
```

`purser gh attach` writes configuration only. `purser gh sync` is the first actual synchronization step.

## Ralph Loop

Purser supports a repeatable execution loop for draining open work:

1. Run `bd ready`
2. Claim one ready bead
3. Implement it
4. Run quality gates
5. Close it
6. Continue until no safe ready beads remain

This repo refers to that pattern as the Ralph loop.

Work-state policy:

- Beads is the authoritative record of work, decomposition, dependencies, and completion state.
- DuckDB memory is for reusable decisions, learnings, failed attempts, and context that future agents should recover without rereading large histories.
- GitHub, when configured, is a synchronized remote representation of the Beads work graph and project state.

## GitHub Integration

Purser has an optional GitHub integration layer for repos and Projects. When enabled,
agents are expected to use it as part of normal workflow rather than treating it as a
manual afterthought.

Typical agent workflow when GitHub integration is enabled:

1. Run `purser gh status` at session start
2. Run `purser gh sync` before starting a larger batch if local and remote may have diverged
3. Perform the normal Beads Ralph loop
4. Run `purser gh sync` again after changing work state so GitHub Issues and Project items stay current

If you only need one direction:

- `purser gh push` to publish local Beads changes
- `purser gh pull` to import remote GitHub changes

## VS Code

VS Code is now the strongest augmentation target because it supports:

- `AGENTS.md`
- custom agents in `.github/agents`
- slash-command prompt files in `.github/prompts`
- preview hook support for agent loops
- background agent sessions

This repository includes a working scaffold:

- [`.github/prompts/purser-build-all.prompt.md`](/home/md/src/repos/purser-2/.github/prompts/purser-build-all.prompt.md)
- [`.github/agents/purser-build-all.agent.md`](/home/md/src/repos/purser-2/.github/agents/purser-build-all.agent.md)
- [`.github/agents/purser-worker.agent.md`](/home/md/src/repos/purser-2/.github/agents/purser-worker.agent.md)
- [`scripts/vscode/purser_stop_hook.py`](/home/md/src/repos/purser-2/scripts/vscode/purser_stop_hook.py)
- [`scripts/vscode/purser_post_tool_hook.py`](/home/md/src/repos/purser-2/scripts/vscode/purser_post_tool_hook.py)

To scaffold the same setup into another repo:

```bash
purser launch vscode
purser launch claude
purser launch codex
```

Then enable:

```json
{
  "chat.useAgentsMdFile": true,
  "chat.useCustomAgentHooks": true
}
```

After that, run `/purser-build-all` in VS Code chat or a background agent session.
If GitHub integration is enabled for the repo, the agent should also check `purser gh status`
and sync before and after a larger work batch.

## Codex CLI

Codex does not use VS Code prompt files. In this repo, the closest equivalent is a
repo-local skill scaffolded under [`.codex/skills/purser-build-all/SKILL.md`](/home/md/src/repos/purser-2/.codex/skills/purser-build-all/SKILL.md),
kept consistent with the VS Code and Claude variants from the same generator code.
Codex should still treat Purser as the workflow engine:

```bash
bd prime
bd ready
bd update <id> --claim
bd show <id>
purser lint
bd close <id> --reason "..."
```

Repeat until the ready queue is exhausted.

Use `purser memory` only when a decision or finding is worth carrying across sessions or smaller context windows. Routine work progress should remain in Beads, commits, and the codebase.
If GitHub integration is enabled, Codex should also run `purser gh status` at session start and `purser gh sync` after meaningful work-state changes.

## Claude Code

Claude Code uses the same Purser and Beads commands, plus host-native files in:

- [`.claude/commands/purser-build-all.md`](/home/md/src/repos/purser-2/.claude/commands/purser-build-all.md)
- [`.claude/agents/purser-build-all.md`](/home/md/src/repos/purser-2/.claude/agents/purser-build-all.md)
- [`.claude/agents/purser-worker.md`](/home/md/src/repos/purser-2/.claude/agents/purser-worker.md)

Those are generated from the same shared command definitions as the VS Code prompt and
Codex skill so the behavior stays aligned. If GitHub integration is enabled, Claude Code
should follow the same sync policy.

## Tool-Specific Instructions

Purser can emit host-oriented instructions:

```bash
purser launch instructions worker --tool vscode
purser launch instructions worker --tool codex
purser launch instructions worker --tool claude
```

## More

The detailed augmentation model is documented in
[docs/agent-augmentation.md](/home/md/src/repos/purser-2/docs/agent-augmentation.md).
