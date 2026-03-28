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
            "Use `purser work discover <title> --from-issue <id>` to file "
            "unrelated problems you notice. Always work on ONE task at a time. "
            "\n\nMemory Systems:\n"
            "1. File-based (AGENTS.md) - Use for simple rules and global dictates that rarely change\n"
            "2. DuckDB (`purser memory store/query`) - Use for detailed session data, "
            "reasoned decisions, and execution context to share across agents"
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
        workspace_root
        / ".github"
        / "prompts"
        / "purser-build-all.prompt.md": _vscode_build_all_prompt(),
        workspace_root / "scripts" / "vscode" / "purser_stop_hook.py": _vscode_stop_hook_script(),
        workspace_root
        / "scripts"
        / "vscode"
        / "purser_post_tool_hook.py": _vscode_post_tool_hook_script(),
        workspace_root / "docs" / "agent-augmentation.md": _agent_augmentation_doc(),
    }

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
- `{purser_bin} --json <command>` — Get JSON output for any command
- `{purser_bin} memory store <key> <value>` — Save context for later
- `{purser_bin} memory query <text>` — Recall saved context
- `{purser_bin} lint` — Validate code quality (ruff + ty)
- `{purser_bin} sync` — Persist all state

## Workflow
1. Intake raw specs and produce structured markdown
2. Decompose specs into epics -> features -> tasks with dependencies
3. Store planning decisions in memory for worker agents

## Memory Management

You have access to TWO memory systems:

### 1. File-based / Conventional Memory
Use for: Simple rules, global/absolute dictates, stable preferences that rarely change
- AGENTS.md or project memory files
- High-level workflow guidance
- "Always do X" type instructions

### 2. DuckDB Memory Store (`{purser_bin} memory`)
Use for: Detailed/structured session data, reasoned decisions, execution context
- Store: `purser memory store <key> <value> --namespace <ns>`
- Query: `purser memory query <text>`
- Examples:
  - Planning decisions and trade-offs made during spec decomposition
  - Context about why a particular approach was chosen
  - Session-specific knowledge to pass to worker agents
  - Structured data like dependency analysis results

**Guideline**: Use file-based memory for "rules that never change." Use DuckDB memory for "context that varies by session/spec."
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
- `{purser_bin} --json <command>` — Get JSON output for any command
- `{purser_bin} memory store <key> <value>` — Save execution context
- `{purser_bin} memory query <text>` — Recall context from PM or prior workers
- `{purser_bin} lint` — Validate code quality before closing
- `{purser_bin} lint --fix` — Auto-fix lint/format issues
- `{purser_bin} sync` — Persist all state

## Workflow
1. Run `{purser_bin} work next` to find available work
2. Run `{purser_bin} work claim <id>` to take ownership
3. Implement the task
4. Run `{purser_bin} lint` to validate code quality
5. If you notice unrelated problems: `{purser_bin} work discover <title> --from-issue <id>`
6. Run `{purser_bin} work done <id> --reason "what was done"`

## Rules
- Work on exactly ONE task per session
- Never fix unrelated problems inline — file them as discoveries
- Always lint before closing
- Always close your task — either completed or with a blocker reason

## Memory Management

You have access to TWO memory systems:

### 1. File-based / Conventional Memory
Use for: Simple rules, global/absolute dictates, stable preferences that rarely change
- AGENTS.md or project memory files
- High-level workflow guidance
- "Always do X" type instructions

### 2. DuckDB Memory Store (`{purser_bin} memory`)
Use for: Detailed/structured session data, execution context, task-specific findings
- Store: `purser memory store <key> <value> --namespace <ns>`
- Query: `purser memory query <text>`
- Examples:
  - Complex debugging steps taken and their outcomes
  - Reasoning about implementation choices
  - Discoveries made during work that could help future agents
  - Context to pass to subsequent tasks in the same molecule

**Guideline**: Use file-based memory for "rules that never change." Use DuckDB memory for "context specific to this task or session."
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
            "executor. Use `bd` and `purser` commands directly from the terminal, "
            "and emulate the Ralph loop manually: pick a ready bead, complete it, "
            "lint/test, close it, then continue with the next ready bead."
        )
    if tool == "claude":
        return (
            "Host environment: Claude Code.\n\n"
            "Use `AGENTS.md` plus optional `.claude/agents` files for persona-level "
            "guidance. Run the same Purser and `bd` commands directly; Claude Code "
            "does not need Purser to own the agent loop to follow the workflow."
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
2. Accept a specific bead ID if one is provided; otherwise run `bd ready`.
3. Claim exactly one bead with `bd update <id> --claim`.
4. Read the issue details with `bd show <id>`.
5. Implement only the scoped work for that bead.
6. Run quality gates before closing the bead.
7. Close the bead with `bd close <id> --reason "<what changed>"`.

Do not create ad hoc TODO files. Use `bd` for task tracking. Do not stop with unpushed work.
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

1. Run `bd ready` and pick the highest-priority ready bead.
2. Claim it with `bd update <id> --claim`.
3. Read it with `bd show <id>`.
4. Implement the bead completely, staying within scope.
5. Run relevant quality gates.
6. Close it with `bd close <id> --reason "<what changed>"`.
7. Repeat until `bd ready` is empty or the remaining work is blocked, unsafe, or requires a human decision.

Rules:

- Work through beads sequentially, one claimed bead at a time.
- If you discover unrelated work, file a new bead instead of expanding scope.
- Summarize completed, blocked, and newly discovered work before finishing.
- Do not stop early just because one bead completed; continue until the queue is exhausted or there is a clear blocker.
"""


def _vscode_build_all_prompt() -> str:
    return """\
---
name: purser-build-all
description: Execute a Purser Ralph loop over all ready beads.
argument-hint: Optional scope guardrails, for example "stop after frontend work" or "only docs and tests".
agent: Purser Build All
tools: ['editFiles', 'runCommands', 'terminalLastCommand', 'changes', 'problems', 'search']
---
Run a Purser Ralph loop in this workspace.

Before you start, load [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md).

Execution policy:

- Work only from the Beads queue.
- Repeatedly run `bd ready`, claim one bead, complete it, lint/test, close it, and move to the next ready bead.
- Keep going until no safe ready beads remain.
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
- quality checks via `purser lint`

## Ralph Loop

In Purser terms, a Ralph loop means:

1. Inspect the ready queue with `bd ready`
2. Claim one bead with `bd update <id> --claim`
3. Implement the bead
4. Run quality gates
5. Close the bead with `bd close <id> --reason "..."`
6. Repeat until no safe ready beads remain

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
"""
