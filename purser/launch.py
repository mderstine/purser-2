"""Launch integration for external coding agents (opencode, claude-code, codex, etc.).

Generates configuration files that wire purser's CLI tools into external agents,
so they can call `purser lint`, `purser work next`, etc. as part of their workflow.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any


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
            "unrelated problems you notice. Always work on ONE task at a time."
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


def generate_agent_instructions(role: str = "worker") -> str:
    """Generate agent instructions for any external coding tool.

    Returns a markdown string that can be injected into any agent's
    system prompt or instructions file (AGENTS.md, .codex, etc.).
    """
    purser_bin = _find_purser_bin()

    if role == "pm":
        return f"""\
# Purser PM Agent Instructions

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
"""

    return f"""\
# Purser Worker Agent Instructions

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
"""
