"""Tests for launch scaffolding and instruction generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from purser.launch import (
    generate_agent_instructions,
    generate_claude_workspace,
    generate_codex_workspace,
    generate_vscode_workspace,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_generate_agent_instructions_for_vscode() -> None:
    instructions = generate_agent_instructions("worker", tool="vscode")
    assert "Host environment: VS Code chat/agent mode." in instructions
    assert "/purser-build-all" in instructions


def test_generate_agent_instructions_for_codex() -> None:
    instructions = generate_agent_instructions("worker", tool="codex")
    assert "Host environment: Codex CLI." in instructions
    assert ".codex/skills" in instructions


def test_generate_vscode_workspace(tmp_path: Path) -> None:
    written = generate_vscode_workspace(workspace_root=tmp_path)
    paths = {path.relative_to(tmp_path).as_posix() for path in written}

    assert ".github/agents/purser-worker.agent.md" in paths
    assert ".github/agents/purser-build-all.agent.md" in paths
    assert ".github/prompts/purser-build-all.prompt.md" in paths
    assert "scripts/vscode/purser_stop_hook.py" in paths
    assert "scripts/vscode/purser_post_tool_hook.py" in paths
    assert "docs/agent-augmentation.md" in paths

    prompt = (tmp_path / ".github" / "prompts" / "purser-build-all.prompt.md").read_text()
    assert "agent: Purser Build All" in prompt
    assert "Ralph loop" in prompt

    stop_hook = (tmp_path / "scripts" / "vscode" / "purser_stop_hook.py").read_text()
    assert "stop_hook_active" in stop_hook
    assert "Continue the Purser Ralph loop." in stop_hook


def test_generate_claude_workspace(tmp_path: Path) -> None:
    written = generate_claude_workspace(workspace_root=tmp_path)
    paths = {path.relative_to(tmp_path).as_posix() for path in written}

    assert ".claude/agents/purser-worker.md" in paths
    assert ".claude/agents/purser-build-all.md" in paths
    assert ".claude/commands/purser-build-all.md" in paths
    assert "docs/agent-augmentation.md" in paths

    command = (tmp_path / ".claude" / "commands" / "purser-build-all.md").read_text()
    assert "Run a Purser Ralph loop in this workspace." in command
    assert "commands/tests run" in command


def test_generate_codex_workspace(tmp_path: Path) -> None:
    written = generate_codex_workspace(workspace_root=tmp_path)
    paths = {path.relative_to(tmp_path).as_posix() for path in written}

    assert ".codex/skills/purser-build-all/SKILL.md" in paths
    assert "docs/agent-augmentation.md" in paths

    skill = (tmp_path / ".codex" / "skills" / "purser-build-all" / "SKILL.md").read_text()
    assert "Use this skill when the user wants the Codex equivalent" in skill
    assert "Run a Purser Ralph loop" in skill
