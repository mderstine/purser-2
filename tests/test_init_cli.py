"""Tests for `purser init` setup and status behavior."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from purser.cli import cli
from purser.gh.cli import GhAvailability


def test_init_check_reports_local_and_github_state(monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("specs").mkdir()
        Path("formulas").mkdir()
        Path(".purser").mkdir()
        Path(".purser/memory.duckdb").touch()
        Path(".purser/gh_sync.duckdb").touch()
        Path(".beads").mkdir()
        Path("purser.toml").write_text(
            '[github]\nenabled = true\nrepo = "owner/repo"\nproject = "Roadmap"\n'
        )

        monkeypatch.setattr(
            "purser.gh.cli.check_gh_availability",
            lambda: GhAvailability.AVAILABLE,
        )

        result = runner.invoke(cli, ["init", "--check"])

        assert result.exit_code == 0
        assert "Config file: purser.toml" in result.output
        assert "Beads repo: ✓ .beads" in result.output
        assert "gh CLI: available" in result.output
        assert "GitHub integration: enabled" in result.output
        assert "GitHub repo: owner/repo" in result.output
        assert "GitHub project: Roadmap" in result.output
        assert "GitHub sync DB: ✓ .purser/gh_sync.duckdb" in result.output


def test_init_with_github_writes_config(monkeypatch) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        monkeypatch.setattr(
            "purser.gh.cli.check_gh_availability",
            lambda: GhAvailability.AVAILABLE,
        )
        monkeypatch.setattr(
            "purser.gh.cli.detect_default_repo",
            lambda cwd=None: "owner/repo",
        )
        monkeypatch.setattr("purser.cli._check_recommended_tools", lambda: None)

        def fake_init_beads(path=None) -> None:
            Path(".beads").mkdir(exist_ok=True)

        monkeypatch.setattr("purser.beads.init_beads", fake_init_beads)

        result = runner.invoke(
            cli,
            [
                "init",
                "--with-github",
                "--repo",
                "owner/repo",
                "--project",
                "Roadmap",
            ],
        )

        assert result.exit_code == 0
        assert "Configured: GitHub integration in purser.toml" in result.output
        assert "Repository: owner/repo" in result.output
        assert "Project: Roadmap" in result.output
        assert "Next: purser gh sync" in result.output

        config = Path("purser.toml").read_text()
        assert '[github]' in config
        assert 'enabled = true' in config
        assert 'repo = "owner/repo"' in config
        assert 'project = "Roadmap"' in config
