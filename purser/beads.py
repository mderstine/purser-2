"""Wrapper around the `bd` (beads) CLI.

All beads interaction is centralized here. Every function shells out to
`bd ... --json`, parses the response, and returns Pydantic models.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING, Any

from purser.models import Issue, Molecule, MolProgress

if TYPE_CHECKING:
    from pathlib import Path


class BeadsError(Exception):
    """Raised when a bd command fails."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"bd command failed ({returncode}): {stderr}")


def _find_bd() -> str:
    """Find the bd binary."""
    path = shutil.which("bd")
    if not path:
        raise FileNotFoundError("bd (beads) CLI not found. Install it: brew install beads")
    return path


def run_bd(
    args: list[str],
    *,
    json_output: bool = True,
    cwd: Path | None = None,
) -> dict[str, Any] | list[Any] | str:
    """Run a bd command and return parsed output."""
    cmd = [_find_bd(), *args]
    if json_output and "--json" not in args:
        cmd.append("--json")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
    )

    if result.returncode != 0:
        raise BeadsError(cmd, result.returncode, result.stderr.strip())

    if json_output:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return result.stdout.strip()

    return result.stdout.strip()


def init_beads(path: Path | None = None) -> None:
    """Initialize beads in a project directory."""
    run_bd(["init"], json_output=False, cwd=path)


def create_issue(
    title: str,
    *,
    type: str = "task",
    description: str | None = None,
    priority: int | None = None,
    parent: str | None = None,
    labels: list[str] | None = None,
    deps: list[str] | None = None,
) -> Issue:
    """Create a new bd issue."""
    args = ["create", title, "-t", type]
    if description:
        args.extend(["-d", description])
    if priority is not None:
        args.extend(["-p", str(priority)])
    if parent:
        args.extend(["--parent", parent])
    if labels:
        for label in labels:
            args.extend(["-l", label])
    if deps:
        for dep in deps:
            args.extend(["--deps", dep])

    data = run_bd(args)
    return Issue.model_validate(data)


def update_issue(issue_id: str, **kwargs: Any) -> Issue:
    """Update a bd issue."""
    args = ["update", issue_id]
    field_flags = {
        "title": "--title",
        "description": "-d",
        "priority": "-p",
        "type": "-t",
        "assignee": "--assignee",
    }
    for field, flag in field_flags.items():
        if field in kwargs:
            args.extend([flag, str(kwargs[field])])
    if kwargs.get("labels"):
        for label in kwargs["labels"]:
            args.extend(["-l", label])

    data = run_bd(args)
    return Issue.model_validate(data)


def close_issue(issue_id: str, reason: str | None = None) -> Issue:
    """Close a bd issue."""
    args = ["close", issue_id]
    if reason:
        args.extend(["--reason", reason])
    data = run_bd(args)
    return Issue.model_validate(data)


def show_issue(issue_id: str) -> Issue:
    """Show details of a bd issue."""
    data = run_bd(["show", issue_id])
    return Issue.model_validate(data)


def list_issues(**filters: Any) -> list[Issue]:
    """List bd issues with optional filters."""
    args = ["list"]
    if filters.get("status"):
        args.extend(["--status", filters["status"]])
    if filters.get("type"):
        args.extend(["-t", filters["type"]])
    if filters.get("assignee"):
        args.extend(["--assignee", filters["assignee"]])
    if filters.get("label"):
        args.extend(["-l", filters["label"]])
    if filters.get("parent"):
        args.extend(["--parent", filters["parent"]])

    data = run_bd(args)
    if isinstance(data, list):
        return [Issue.model_validate(item) for item in data]
    return []


def ready_issues(limit: int = 10, mol: str | None = None) -> list[Issue]:
    """Get unblocked issues ready for work."""
    args = ["ready"]
    if mol:
        args.extend(["--mol", mol])

    data = run_bd(args)
    if isinstance(data, list):
        return [Issue.model_validate(item) for item in data][:limit]
    return []


def claim_issue(issue_id: str) -> Issue:
    """Claim an issue (set to in_progress)."""
    args = ["update", issue_id, "--claim"]
    data = run_bd(args)
    return Issue.model_validate(data)


def add_dependency(
    from_id: str,
    to_id: str,
    dep_type: str = "blocks",
) -> None:
    """Add a dependency between issues."""
    run_bd(["dep", "add", from_id, dep_type, to_id], json_output=False)


def pour_formula(
    formula_path: str,
    vars: dict[str, str] | None = None,
) -> Molecule:
    """Instantiate a formula as a molecule."""
    args = ["mol", "pour", formula_path]
    if vars:
        for k, v in vars.items():
            args.extend(["--var", f"{k}={v}"])

    data = run_bd(args)
    return Molecule.model_validate(data)


def show_molecule(mol_id: str) -> Molecule:
    """Show a molecule's details."""
    data = run_bd(["mol", "show", mol_id])
    return Molecule.model_validate(data)


def mol_progress(mol_id: str) -> MolProgress:
    """Get molecule progress summary."""
    data = run_bd(["mol", "progress", mol_id])
    return MolProgress.model_validate(data)


def prime() -> str:
    """Get beads context for session start."""
    return str(run_bd(["prime", "--full"], json_output=False))


def dep_tree(issue_id: str) -> str:
    """Show dependency tree for an issue."""
    return str(run_bd(["dep", "tree", issue_id], json_output=False))


def note_issue(issue_id: str, text: str) -> None:
    """Add a note to an issue."""
    run_bd(["note", issue_id, text], json_output=False)


def search_issues(query: str) -> list[Issue]:
    """Search issues by text."""
    data = run_bd(["search", query])
    if isinstance(data, list):
        return [Issue.model_validate(item) for item in data]
    return []


def sync() -> None:
    """Sync beads state."""
    run_bd(["sync"], json_output=False)
