"""Lint runner: ruff + ty checks callable by any agent.

This module wraps the Astral toolchain (ruff for linting/formatting, ty for
type checking) so that any LLM agent — Claude, Codex, Gemini, Ollama, etc. —
can validate code quality via `purser lint` or the `purser_lint` tool.

All tools are invoked via `uv run` to ensure they use the project's virtualenv
and pinned versions.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


def _find_uv() -> str:
    """Find the uv binary."""
    path = shutil.which("uv")
    if not path:
        raise FileNotFoundError("uv not found. Install it: https://docs.astral.sh/uv/")
    return path


def _run(cmd: list[str], *, cwd: str | None = None) -> tuple[int, str]:
    """Run a command and return (exit_code, combined output)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def run_lint(
    *,
    target: str = ".",
    fix: bool = False,
) -> dict[str, Any]:
    """Run all lint checks and return structured results.

    Args:
        target: Path to check (default: current directory).
        fix: If True, auto-fix ruff lint issues and reformat.

    Returns:
        Dict with keys: passed (bool), checks (list), total_count, failed_count.
        Each check has: name, passed (bool), output (str), exit_code (int).
    """
    uv = _find_uv()
    checks: list[dict[str, Any]] = []

    # 1. ruff lint (with optional --fix)
    ruff_lint_cmd = [uv, "run", "ruff", "check", target]
    if fix:
        ruff_lint_cmd.append("--fix")
    rc, output = _run(ruff_lint_cmd)
    checks.append(
        {
            "name": "ruff check" + (" --fix" if fix else ""),
            "passed": rc == 0,
            "output": output if rc != 0 else "",
            "exit_code": rc,
        }
    )

    # 2. ruff format (check or apply)
    if fix:
        ruff_fmt_cmd = [uv, "run", "ruff", "format", target]
    else:
        ruff_fmt_cmd = [uv, "run", "ruff", "format", "--check", target]
    rc, output = _run(ruff_fmt_cmd)
    checks.append(
        {
            "name": "ruff format" + ("" if fix else " --check"),
            "passed": rc == 0,
            "output": output if rc != 0 else "",
            "exit_code": rc,
        }
    )

    # 3. ty type check (no fix mode)
    ty_cmd = [uv, "run", "ty", "check"]
    rc, output = _run(ty_cmd)
    checks.append(
        {
            "name": "ty check",
            "passed": rc == 0,
            "output": output if rc != 0 else "",
            "exit_code": rc,
        }
    )

    failed = [c for c in checks if not c["passed"]]
    return {
        "passed": len(failed) == 0,
        "checks": checks,
        "total_count": len(checks),
        "failed_count": len(failed),
    }
