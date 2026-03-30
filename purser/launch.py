"""Launch integration for external coding agents (opencode, claude-code, codex, etc.).

Generates configuration files and workspace scaffolding that wire Purser's CLI
into external agents, so they can call `purser lint`, `purser work next`, and
other workflow commands as part of their execution loop.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

COMMAND_SPECS: tuple[dict[str, str], ...] = (
    {
        "name": "purser-add-spec",
        "description": "Create a new structured Purser spec from a feature description.",
        "argument_hint": "Provide the feature description or requirement to turn into a spec.",
    },
    {
        "name": "purser-build",
        "description": "Claim and build the next ready bead from the queue.",
        "argument_hint": "Optional bead ID or scope guardrails if you do not want the default next ready item.",
    },
    {
        "name": "purser-build-all",
        "description": "Execute a Purser Ralph loop over all ready beads.",
        "argument_hint": (
            'Optional scope guardrails, for example "stop after frontend work" '
            'or "only docs and tests".'
        ),
    },
    {
        "name": "purser-init",
        "description": "Initialize Purser in the current repository and report setup status.",
        "argument_hint": "Optional flags or intent, for example check-only, force re-init, or with GitHub setup.",
    },
    {
        "name": "purser-plan",
        "description": "Decompose one or more specs into Beads work items.",
        "argument_hint": "Optional spec ID; if omitted, plan the relevant unplanned specs.",
    },
)


def _write_text(path: Path, content: str, *, force: bool = False) -> bool:
    """Write a file if it is missing, or overwrite when force is enabled."""
    if path.exists() and not force:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return True


def _find_purser_bin() -> str:
    """Find the purser binary path."""
    path = shutil.which("purser")
    if path:
        return path
    # Fallback: uv run purser
    uv = shutil.which("uv")
    if uv:
        return f"{uv} run purser"
    return "purser"


def generate_opencode_config(
    *,
    model: str = "qwen3-coder:480b-cloud",
    provider: str = "ollama-cloud",
    base_url: str = "https://ollama.com/v1",
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate an opencode configuration that integrates purser tools.

    Creates/updates ~/.config/opencode/opencode.json with:
    - Ollama Cloud as the LLM provider
    - Purser CLI commands as custom tools
    - Project context injection

    Returns the generated config dict.
    """
    config: dict[str, Any] = {
        "provider": {
            "id": "@ai-sdk/openai-compatible",
            "options": {
                "baseURL": base_url,
                "name": provider,
            },
        },
        "model": model,
        "mcpServers": {},
        "customInstructions": (
            "You have access to purser CLI for project management. "
            "Use `purser work next` to find ready tasks, `purser work claim <id>` "
            "to claim one, and `purser work done <id>` when finished. "
            "Use `purser lint` to validate code quality before closing tasks. "
            "If GitHub integration is enabled, use `purser gh status` and "
            "`purser gh sync` to keep GitHub Issues and Projects aligned with Beads. "
            "Use `purser work discover <title> --from-issue <id>` to file "
            "unrelated problems you notice. Always work on ONE task at a time. "
            "\n\nMemory Systems:\n"
            "1. Beads (`bd`) - Use as the authoritative work record for decomposition, "
            "status, dependencies, and discoveries\n"
            "2. DuckDB (`purser memory store/query`) - Use for reusable decisions, "
            "learnings, failed approaches, and execution context to share across agents"
        ),
    }

    # Add OLLAMA_API_KEY reference if set
    api_key = os.environ.get("OLLAMA_API_KEY")
    if api_key:
        config["provider"]["options"]["apiKey"] = "${OLLAMA_API_KEY}"

    # Write config
    if output_path is None:
        output_path = Path.home() / ".config" / "opencode" / "opencode.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Merge with existing config if present
    if output_path.exists():
        existing = json.loads(output_path.read_text())
        # Preserve user's custom settings, overlay purser-specific ones
        existing.update(config)
        config = existing

    output_path.write_text(json.dumps(config, indent=2) + "\n")
    return config


def generate_vscode_workspace(
    *,
    workspace_root: Path,
    force: bool = False,
) -> list[Path]:
    """Scaffold VS Code prompt, agent, and hook files for Purser workflows."""
    files: dict[Path, str] = {
        workspace_root / ".github" / "agents" / "purser-worker.agent.md": _vscode_worker_agent(),
        workspace_root
        / ".github"
        / "agents"
        / "purser-build-all.agent.md": _vscode_build_all_agent(),
        workspace_root / "scripts" / "vscode" / "purser_stop_hook.py": _vscode_stop_hook_script(),
        workspace_root
        / "scripts"
        / "vscode"
        / "purser_post_tool_hook.py": _vscode_post_tool_hook_script(),
        workspace_root / "docs" / "agent-augmentation.md": _agent_augmentation_doc(),
    }
    for command in COMMAND_SPECS:
        files[
            workspace_root
            / ".github"
            / "prompts"
            / f"{command['name']}.prompt.md"
        ] = _vscode_prompt(command)

    written: list[Path] = []
    for path, content in files.items():
        if _write_text(path, content, force=force):
            written.append(path)

    return written


def generate_claude_workspace(
    *,
    workspace_root: Path,
    force: bool = False,
) -> list[Path]:
    """Scaffold Claude Code command and agent files for Purser workflows."""
    files: dict[Path, str] = {
        workspace_root / ".claude" / "agents" / "purser-worker.md": _claude_worker_agent(),
        workspace_root / ".claude" / "agents" / "purser-build-all.md": _claude_build_all_agent(),
        workspace_root / "docs" / "agent-augmentation.md": _agent_augmentation_doc(),
    }
    for command in COMMAND_SPECS:
        files[
            workspace_root
            / ".claude"
            / "commands"
            / f"{command['name']}.md"
        ] = _claude_command(command)

    written: list[Path] = []
    for path, content in files.items():
        if _write_text(path, content, force=force):
            written.append(path)

    return written


def generate_codex_workspace(
    *,
    workspace_root: Path,
    force: bool = False,
) -> list[Path]:
    """Scaffold Codex skill files that mirror the shared Purser commands."""
    files: dict[Path, str] = {
        workspace_root / "docs" / "agent-augmentation.md": _agent_augmentation_doc(),
    }
    for command in COMMAND_SPECS:
        files[
            workspace_root
            / ".codex"
            / "skills"
            / command["name"]
            / "SKILL.md"
        ] = _codex_skill(command)

    written: list[Path] = []
    for path, content in files.items():
        if _write_text(path, content, force=force):
            written.append(path)

    return written


def generate_agent_instructions(role: str = "worker", tool: str = "generic") -> str:
    """Generate agent instructions for external coding tools.

    Returns a markdown string that can be injected into any agent's
    system prompt or instructions file (AGENTS.md, .codex, etc.).
    """
    purser_bin = _find_purser_bin()
    tool = tool.lower()
    tool_preamble = _tool_preamble(tool)

    if role == "pm":
        return f"""\
# Purser PM Agent Instructions

{tool_preamble}

You are a Project Manager agent. Use the purser CLI for all task management.

## Available Commands
- `{purser_bin} spec intake <file>` — Ingest a raw spec into structured markdown
- `{purser_bin} spec list` — List all specs
- `{purser_bin} spec show <id>` — Show a spec
- `{purser_bin} plan create <spec_id>` — Decompose spec into epics/features/tasks
- `{purser_bin} plan show <id>` — Show plan dependency tree
- `{purser_bin} gh status|sync|push|pull` — Keep GitHub Issues/Projects aligned when GitHub integration is enabled
- `{purser_bin} --json <command>` — Get JSON output for any command
- `{purser_bin} memory store <key> <value>` — Save context for later
- `{purser_bin} memory query <text>` — Recall saved context
- `{purser_bin} lint` — Validate code quality (ruff + ty)
- `{purser_bin} sync` — Persist all state

## Workflow
1. Intake raw specs and produce structured markdown
2. Decompose specs into epics -> features -> tasks with dependencies
3. If GitHub integration is enabled, sync planning changes to GitHub
4. Store planning decisions in memory for worker agents

## Memory Management

You have access to TWO persistence systems:

### 1. Beads (`bd`)
Use for: the authoritative work record
- Spec decomposition into epics, features, and tasks
- Dependencies, discoveries, and blockers
- Current state of what is open, in progress, or closed
- Anything that changes the project work graph

### 2. DuckDB Memory Store (`{purser_bin} memory`)
Use for: reusable context that helps future agents work with smaller context windows
- Store: `purser memory store <key> <value> --namespace <ns>`
- Query: `purser memory query <text>`
- Examples:
  - Planning decisions and trade-offs made during spec decomposition
  - Context about why a particular approach was chosen
  - Session-specific knowledge to pass to worker agents
  - Failed approaches or debugging learnings worth reusing

**Guideline**: If it changes work state, put it in Beads. If it captures reusable understanding, put it in DuckDB memory.
"""

    return f"""\
# Purser Worker Agent Instructions

{tool_preamble}

You are a Worker agent. You claim ONE task, execute it, and close it.

## Available Commands
- `{purser_bin} work next` — Find ready (unblocked) tasks
- `{purser_bin} work claim <id>` — Claim a task
- `{purser_bin} work done <id> --reason "..."` — Close a completed task
- `{purser_bin} work discover <title> --from-issue <id>` — File unrelated problems
- `{purser_bin} gh status|sync|push|pull` — Keep GitHub Issues/Projects aligned when GitHub integration is enabled
- `{purser_bin} --json <command>` — Get JSON output for any command
- `{purser_bin} memory store <key> <value>` — Save execution context
- `{purser_bin} memory query <text>` — Recall context from PM or prior workers
- `{purser_bin} lint` — Validate code quality before closing
- `{purser_bin} lint --fix` — Auto-fix lint/format issues
- `{purser_bin} sync` — Persist all state

## Workflow
1. If GitHub integration is enabled, run `{purser_bin} gh status` at session start
2. Run `{purser_bin} work next` to find available work
3. Run `{purser_bin} work claim <id>` to take ownership
4. Implement the task
5. Run `{purser_bin} lint` to validate code quality
6. Run `{purser_bin} gh sync` after meaningful work-state changes when GitHub integration is enabled
7. If you notice unrelated problems: `{purser_bin} work discover <title> --from-issue <id>`
8. Run `{purser_bin} work done <id> --reason "what was done"`

## Rules
- Work on exactly ONE task per session
- Never fix unrelated problems inline — file them as discoveries
- Always lint before closing
- Always close your task — either completed or with a blocker reason

## Memory Management

You have access to TWO persistence systems:

### 1. Beads (`bd`)
Use for: the authoritative work record
- Task status, scope, dependencies, blockers, and discoveries
- Notes about the work item itself
- Anything that changes the queue or task graph

### 2. DuckDB Memory Store (`{purser_bin} memory`)
Use for: reusable context that should survive this session
- Store: `purser memory store <key> <value> --namespace <ns>`
- Query: `purser memory query <text>`
- Examples:
  - Complex debugging steps taken and their outcomes
  - Reasoning about implementation choices
  - Discoveries made during work that could help future agents
  - Context to pass to subsequent tasks in the same molecule

**Guideline**: Keep routine work state in Beads. Store DuckDB memory only when it will help later agents avoid re-deriving important context.
"""


def _tool_preamble(tool: str) -> str:
    """Describe how a host tool should use Purser."""
    if tool == "vscode":
        return (
            "Host environment: VS Code chat/agent mode.\n\n"
            "Prefer workspace-level customizations in `.github/agents`, "
            "`.github/prompts`, `.github/hooks`, and `AGENTS.md`. When available, "
            "run `/purser-build-all` in a background agent session to iterate over "
            "ready beads until the queue is empty or remaining work is blocked."
        )
    if tool == "codex":
        return (
            "Host environment: Codex CLI.\n\n"
            "Treat Purser as the workflow engine and the Codex session as the "
            "executor. Use repo-local skills in `.codex/skills` as the reusable "
            "command equivalents, then run the underlying `bd` and `purser` "
            "commands directly from the terminal. Codex does not have the same "
            "native slash-command registry as VS Code or Claude, so emulate the "
            "Ralph loop manually: pick a ready bead, complete it, lint/test, "
            "close it, then continue with the next ready bead."
        )
    if tool == "claude":
        return (
            "Host environment: Claude Code.\n\n"
            "Use `AGENTS.md`, `.claude/agents`, and `.claude/commands` for the "
            "host-native command surface. Run the same Purser and `bd` commands "
            "directly; Claude Code does not need Purser to own the agent loop to "
            "follow the workflow."
        )
    return (
        "Host environment: generic external agent.\n\n"
        "Use Purser as the project workflow layer. The external tool stays in "
        "control of coding while Purser supplies specs, plans, memory, linting, "
        "and bead orchestration."
    )


def _vscode_worker_agent() -> str:
    return """\
---
name: Purser Worker
description: Claim and execute one bead with Purser and Beads.
argument-hint: Provide a bead ID or describe the task boundary you want the worker to respect.
tools: ['editFiles', 'runCommands', 'terminalLastCommand', 'changes', 'problems', 'search']
---
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
"""


def _vscode_build_all_agent() -> str:
    return """\
---
name: Purser Build All
description: Work through ready beads in a Ralph loop until no safe ready work remains.
argument-hint: Optional guardrails, scope limits, or stopping conditions.
tools: ['editFiles', 'runCommands', 'terminalLastCommand', 'changes', 'problems', 'search']
hooks:
  Stop:
    - type: command
      command: "python3 scripts/vscode/purser_stop_hook.py"
  PostToolUse:
    - type: command
      command: "python3 scripts/vscode/purser_post_tool_hook.py"
---
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
"""


def _find_command(name: str) -> dict[str, str]:
    for command in COMMAND_SPECS:
        if command["name"] == name:
            return command
    raise KeyError(name)


def _vscode_build_all_prompt(command: dict[str, str]) -> str:
    return f"""\
---
name: {command["name"]}
description: {command["description"]}
argument-hint: {command["argument_hint"]}
agent: Purser Build All
tools: ['editFiles', 'runCommands', 'terminalLastCommand', 'changes', 'problems', 'search']
---
Run a Purser Ralph loop in this workspace.

Before you start, load [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md).

Execution policy:

- Work only from the Beads queue.
- If GitHub integration is enabled, check `purser gh status` at the start and sync before and after the batch as needed.
- Repeatedly run `bd ready`, claim one bead, complete it, lint/test, close it, and move to the next ready bead.
- Keep going until no safe ready beads remain.
- Use `bd` as the authoritative work record; use `purser memory` only for reusable context and learnings worth carrying across sessions.
- If you stop because the queue is blocked, explain exactly which bead blocked progress and what follow-up is needed.
- End with a compact report of:
  - completed beads
  - blocked or deferred beads
  - discoveries filed
  - commands/tests run
"""


def _vscode_prompt(command: dict[str, str]) -> str:
    if command["name"] == "purser-build-all":
        return _vscode_build_all_prompt(command)
    if command["name"] == "purser-build":
        return f"""\
---
name: {command["name"]}
description: {command["description"]}
argument-hint: {command["argument_hint"]}
agent: Purser Worker
tools: ['editFiles', 'runCommands', 'terminalLastCommand', 'changes', 'problems', 'search']
---
Claim and execute exactly one ready bead in this workspace.

Before you start, load [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md).

Execution policy:

- If a bead ID is provided, respect it. Otherwise run `bd ready` and pick the top safe ready bead.
- Claim the bead with `bd update <id> --claim` before starting work.
- Read the issue with `bd show <id>`, implement only that scope, run relevant quality gates, and close it with `bd close <id> --reason "<what changed>"`.
- If GitHub integration is enabled, check `purser gh status` at the start and sync changed work state back as needed.
- End with the claimed bead ID, what changed, and what tests or lint commands ran.
"""
    if command["name"] == "purser-add-spec":
        return f"""\
---
name: {command["name"]}
description: {command["description"]}
argument-hint: {command["argument_hint"]}
tools: ['runCommands', 'terminalLastCommand', 'search']
---
Create a new Purser spec from the user-provided description.

Before you start, load [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md).

Execution policy:

- Run `uv run purser spec add "<description>"` using the user-provided requirement text.
- If the requirement text is in a file, inspect it first, then feed the relevant description into `purser spec add`.
- Report the created spec ID, title, and file path.
- Offer the follow-up command to inspect or plan it next.
"""
    if command["name"] == "purser-init":
        return f"""\
---
name: {command["name"]}
description: {command["description"]}
argument-hint: {command["argument_hint"]}
tools: ['runCommands', 'terminalLastCommand']
---
Initialize Purser in this repository or report its current setup status.

Before you start, load [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md).

Execution policy:

- Use `uv run purser init` for normal setup.
- Use `uv run purser init --check` when the user wants status without modifying anything.
- Use `uv run purser init --force` only when the user explicitly asks to reinitialize.
- If the user wants GitHub coordination during setup, use `uv run purser init --with-github` plus `--repo` and `--project` when available.
- Report memory DB, specs directory, formulas directory, Beads status, and GitHub status.
"""
    if command["name"] == "purser-plan":
        return f"""\
---
name: {command["name"]}
description: {command["description"]}
argument-hint: {command["argument_hint"]}
tools: ['runCommands', 'terminalLastCommand', 'search']
---
Decompose specs into Beads work items.

Before you start, load [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md).

Execution policy:

- If the user gives a spec ID, run `uv run purser plan create <spec_id>`.
- Otherwise inspect available specs with `uv run purser spec list`, choose the relevant unplanned spec, and run `uv run purser plan create <spec_id>`.
- Report the created epic, feature, and task IDs.
- If the planner output looks incomplete or malformed, say so explicitly instead of pretending the plan is detailed.
"""
    raise KeyError(command["name"])


def _claude_worker_agent() -> str:
    return """\
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
"""


def _claude_build_all_agent() -> str:
    return """\
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
"""


def _claude_command(command: dict[str, str]) -> str:
    if command["name"] == "purser-build-all":
        return f"""\
Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) before you start.

Arguments: {command["argument_hint"]}

Run a Purser Ralph loop in this workspace.

Execution policy:

- Work only from the Beads queue.
- If GitHub integration is enabled, check `purser gh status` at the start and sync before and after the batch as needed.
- Repeatedly run `bd ready`, claim one bead, complete it, lint/test, close it, and move to the next ready bead.
- Keep going until no safe ready beads remain.
- Use `bd` as the authoritative work record; use `purser memory` only for reusable context and learnings worth carrying across sessions.
- If you stop because the queue is blocked, explain exactly which bead blocked progress and what follow-up is needed.
- End with a compact report of:
  - completed beads
  - blocked or deferred beads
  - discoveries filed
  - commands/tests run
"""
    if command["name"] == "purser-build":
        return f"""\
Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) before you start.

Arguments: {command["argument_hint"]}

Claim and execute exactly one ready bead.

- Run `bd ready --limit 1` unless the user names a specific bead.
- Claim the bead with `bd update <id> --claim`, inspect it with `bd show <id>`, implement only that scope, run relevant quality gates, and close it.
- End with the bead ID, what changed, and the validation commands that ran.
"""
    if command["name"] == "purser-add-spec":
        return f"""\
Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) before you start.

Arguments: {command["argument_hint"]}

Create a structured Purser spec from the user-provided requirement text.

- Run `uv run purser spec add "<description>"`.
- Report the created spec ID, title, and file path.
- Offer to inspect it with `uv run purser spec show <id>` or plan it with `uv run purser plan create <id>`.
"""
    if command["name"] == "purser-init":
        return f"""\
Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) before you start.

Arguments: {command["argument_hint"]}

Initialize Purser in the current repository or report setup status.

- Use `uv run purser init` for normal setup.
- Use `uv run purser init --check` for status-only requests.
- Use `uv run purser init --with-github` plus explicit `--repo`/`--project` when the user wants GitHub setup too.
- Report the resulting local and GitHub status clearly.
"""
    if command["name"] == "purser-plan":
        return f"""\
Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) before you start.

Arguments: {command["argument_hint"]}

Decompose one or more specs into Beads work items.

- If the user provides a spec ID, run `uv run purser plan create <spec_id>`.
- Otherwise list specs with `uv run purser spec list`, choose the relevant one, and run the planner.
- Report the created epic, feature, and task IDs.
"""
    return f"""\
Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) before you start.

Arguments: {command["argument_hint"]}

Run a Purser Ralph loop in this workspace.

Execution policy:

- Work only from the Beads queue.
- If GitHub integration is enabled, check `purser gh status` at the start and sync before and after the batch as needed.
- Repeatedly run `bd ready`, claim one bead, complete it, lint/test, close it, and move to the next ready bead.
- Keep going until no safe ready beads remain.
- Use `bd` as the authoritative work record; use `purser memory` only for reusable context and learnings worth carrying across sessions.
- If you stop because the queue is blocked, explain exactly which bead blocked progress and what follow-up is needed.
- End with a compact report of:
  - completed beads
  - blocked or deferred beads
  - discoveries filed
  - commands/tests run
"""


def _codex_skill(command: dict[str, str]) -> str:
    if command["name"] == "purser-build-all":
        return f"""\
---
name: {command["name"]}
description: {command["description"]}
---

# {command["name"]}

Use this skill when the user wants the Codex equivalent of `/{command["name"]}`.

Arguments: {command["argument_hint"]}

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Run a Purser Ralph loop in this workspace.

Execution policy:

- Work only from the Beads queue.
- If GitHub integration is enabled, check `purser gh status` at the start and sync before and after the batch as needed.
- Repeatedly run `bd ready`, claim one bead, complete it, lint/test, close it, and move to the next ready bead.
- Keep going until no safe ready beads remain.
- Use `bd` as the authoritative work record; use `purser memory` only for reusable context and learnings worth carrying across sessions.
- If you stop because the queue is blocked, explain exactly which bead blocked progress and what follow-up is needed.
- End with a compact report of:
  - completed beads
  - blocked or deferred beads
  - discoveries filed
  - commands/tests run
"""
    if command["name"] == "purser-build":
        return f"""\
---
name: {command["name"]}
description: {command["description"]}
---

# {command["name"]}

Use this skill when the user wants the Codex equivalent of `/{command["name"]}`.

Arguments: {command["argument_hint"]}

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Claim and execute exactly one ready bead.

- Run `bd ready --limit 1` unless the user names a specific bead.
- Claim the bead, inspect it, implement only that scope, run relevant validation, and close it.
- Report the bead ID and what changed.
"""
    if command["name"] == "purser-add-spec":
        return f"""\
---
name: {command["name"]}
description: {command["description"]}
---

# {command["name"]}

Use this skill when the user wants the Codex equivalent of `/{command["name"]}`.

Arguments: {command["argument_hint"]}

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Create a structured Purser spec from a requirement description.

- Run `uv run purser spec add "<description>"`.
- Report the created spec ID, title, and file path.
- Offer the follow-up inspection or planning command.
"""
    if command["name"] == "purser-init":
        return f"""\
---
name: {command["name"]}
description: {command["description"]}
---

# {command["name"]}

Use this skill when the user wants the Codex equivalent of `/{command["name"]}`.

Arguments: {command["argument_hint"]}

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Initialize Purser in the current repository or report status.

- Use `uv run purser init` for setup.
- Use `uv run purser init --check` for status-only requests.
- Use `uv run purser init --with-github` plus `--repo`/`--project` when GitHub setup is desired.
- Report local and GitHub setup state clearly.
"""
    if command["name"] == "purser-plan":
        return f"""\
---
name: {command["name"]}
description: {command["description"]}
---

# {command["name"]}

Use this skill when the user wants the Codex equivalent of `/{command["name"]}`.

Arguments: {command["argument_hint"]}

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Decompose specs into Beads work items.

- If a spec ID is provided, run `uv run purser plan create <spec_id>`.
- Otherwise list specs, choose the relevant one, and run the planner.
- Report the created epic, feature, and task IDs.
"""
    return f"""\
---
name: {command["name"]}
description: {command["description"]}
---

# {command["name"]}

Use this skill when the user wants the Codex equivalent of `/{command["name"]}`.

Arguments: {command["argument_hint"]}

Follow [../../../AGENTS.md](../../../AGENTS.md) and [../../../docs/agent-augmentation.md](../../../docs/agent-augmentation.md).

Run a Purser Ralph loop in this workspace.

Execution policy:

- Work only from the Beads queue.
- If GitHub integration is enabled, check `purser gh status` at the start and sync before and after the batch as needed.
- Repeatedly run `bd ready`, claim one bead, complete it, lint/test, close it, and move to the next ready bead.
- Keep going until no safe ready beads remain.
- Use `bd` as the authoritative work record; use `purser memory` only for reusable context and learnings worth carrying across sessions.
- If you stop because the queue is blocked, explain exactly which bead blocked progress and what follow-up is needed.
- End with a compact report of:
  - completed beads
  - blocked or deferred beads
  - discoveries filed
  - commands/tests run
"""


def _vscode_stop_hook_script() -> str:
    return """\
#!/usr/bin/env python3
\"\"\"VS Code Stop hook that nudges the Purser build-all loop to continue.\"\"\"

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_ready(repo_root: Path) -> list[dict]:
    result = subprocess.run(
        ["bd", "ready", "--json"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def main() -> int:
    payload = json.load(sys.stdin)
    repo_root = Path(payload.get("workspace_folder", "."))
    ready = _run_ready(repo_root)
    stop_hook_active = bool(payload.get("stop_hook_active"))

    if not ready:
        print(json.dumps({"systemMessage": "Purser hook: no ready beads remain."}))
        return 0

    if stop_hook_active:
        print(
            json.dumps(
                {
                    "systemMessage": (
                        "Purser hook: ready beads still remain, but the stop hook has "
                        "already re-entered the loop once. Stop if the remaining work "
                        "is intentionally blocked or unsafe."
                    )
                }
            )
        )
        return 0

    next_issue = ready[0]
    issue_id = next_issue.get("id", "unknown")
    title = next_issue.get("title", "next ready bead")
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "decision": "block",
                    "reason": (
                        f"Continue the Purser Ralph loop. Ready bead remains: {issue_id} "
                        f"({title}). Claim it and keep working unless a human decision "
                        "or safety concern prevents progress."
                    ),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _vscode_post_tool_hook_script() -> str:
    return """\
#!/usr/bin/env python3
\"\"\"VS Code PostToolUse hook that reminds the model to run Purser quality gates.\"\"\"

from __future__ import annotations

import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name")

    if tool_name != "editFiles":
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        "You edited files. Before closing the current bead, run the "
                        "relevant quality gates such as `purser lint`, targeted tests, "
                        "and any build commands needed for the touched code."
                    ),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _agent_augmentation_doc() -> str:
    return """\
# Purser Agent Augmentation

Purser is the workflow layer. The host agent stays responsible for coding, terminal
interaction, and applying changes. Purser adds:

- specs via `purser spec ...`
- decomposition via `purser plan ...`
- queueing and state via `bd`
- memory via `purser memory ...`

## Work Record vs Memory

Purser uses two different persistence layers for different jobs:

- Beads is the authoritative work record. Use it for decomposition, dependencies, status, discoveries, and completion.
- DuckDB memory is the reusable context layer. Use `purser memory store/query` for decisions, learnings, failed approaches, debugging context, and other information that should help future agents work with smaller context windows.

Practical rule:

- If it changes the task graph or project state, put it in Beads.
- If it captures reusable understanding, put it in DuckDB memory.
- quality checks via `purser lint`

## Ralph Loop

In Purser terms, a Ralph loop means:

1. Inspect the ready queue with `bd ready`
2. Claim one bead with `bd update <id> --claim`
3. Implement the bead
4. Run quality gates
5. Close the bead with `bd close <id> --reason "..."`
6. Repeat until no safe ready beads remain

Memory is not a mandatory loop step. Store memory only when it would materially help a later bead or later session.

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
- `.github/prompts/purser-add-spec.prompt.md`
- `.github/prompts/purser-build.prompt.md`
- `.github/prompts/purser-build-all.prompt.md`
- `.github/prompts/purser-init.prompt.md`
- `.github/prompts/purser-plan.prompt.md`
- `scripts/vscode/purser_stop_hook.py`
- `scripts/vscode/purser_post_tool_hook.py`

Recommended settings to enable the full workflow:

```json
{
  "chat.useAgentsMdFile": true,
  "chat.useCustomAgentHooks": true
}
```

Use `/purser-add-spec`, `/purser-build`, `/purser-build-all`, `/purser-init`, and
`/purser-plan` from chat as the VS Code command surface for the shared Purser workflow.

While looping:

- Keep work state in `bd`
- Store DuckDB memory only for non-obvious decisions, learnings, blockers, failed attempts, or context that should survive a narrower future session

## Codex CLI

Codex does not use VS Code prompt files or hooks. The closest portable equivalent is
repo-local skills generated under `.codex/skills`, sourced from the same Purser command
definitions as the VS Code and Claude files. The shared Codex-equivalent command set is:

- `purser-add-spec`
- `purser-build`
- `purser-build-all`
- `purser-init`
- `purser-plan`

Codex still follows the workflow from `AGENTS.md` and terminal commands:

1. Run `bd prime`
2. Run `bd ready`
3. Claim one bead
4. Implement it
5. Run `purser lint` and relevant tests
6. Close the bead
7. Continue with the next ready bead

The loop is procedural rather than hook-driven, but the behavior is the same.

Apply the same memory rule: Beads for work state, DuckDB for reusable context.

## Claude Code

Claude Code can use the same `AGENTS.md` instructions and the same `bd`/`purser`
commands. Purser can scaffold host-native Claude files in `.claude/commands` and
`.claude/agents`, sourced from the same command definitions as VS Code prompts and
Codex skills. The key idea is the same:
Purser owns project state, while Claude owns execution inside the current session.

## Design Boundary

Purser should stay generic by separating:

- workflow state and commands, which belong in Purser
- host-specific orchestration, which belongs in VS Code customizations or tool docs

That keeps the framework portable across VS Code, Codex, Claude, and other agent
hosts without making Purser depend on any single vendor UX.
"""
