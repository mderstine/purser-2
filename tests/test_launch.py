"""Tests for launch scaffolding and instruction generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from purser.launch import generate_agent_instructions, generate_vscode_workspace

if TYPE_CHECKING:
    from pathlib import Path


def test_generate_agent_instructions_for_vscode() -> None:
    instructions = generate_agent_instructions("worker", tool="vscode")
    assert "Host environment: VS Code chat/agent mode." in instructions
    assert "/purser-build-all" in instructions


def test_generate_agent_instructions_for_codex() -> None:
    instructions = generate_agent_instructions("worker", tool="codex")
    assert "Host environment: Codex CLI." in instructions
    assert "Ralph loop manually" in instructions


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
