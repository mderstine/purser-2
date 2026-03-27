"""GitHub Labels API wrapper via gh CLI."""

from __future__ import annotations

import contextlib
from typing import Any

from purser.gh.cli import GhCliError, gh_api


def ensure_label(
    repo: str,
    name: str,
    color: str = "ededed",
    description: str = "",
) -> dict[str, Any]:
    """Create a label if it doesn't exist, or return the existing one."""
    try:
        result = gh_api(
            f"/repos/{{owner}}/{{repo}}/labels/{name}",
            repo=repo,
        )
    except GhCliError:
        # Label doesn't exist, create it
        result = gh_api(
            "/repos/{owner}/{repo}/labels",
            method="POST",
            repo=repo,
            json_body={
                "name": name,
                "color": color,
                "description": description,
            },
        )
    assert isinstance(result, dict)
    return result


def add_labels(
    repo: str,
    issue_number: int,
    labels: list[str],
) -> list[dict[str, Any]]:
    """Add labels to an issue."""
    result = gh_api(
        f"/repos/{{owner}}/{{repo}}/issues/{issue_number}/labels",
        method="POST",
        repo=repo,
        json_body={"labels": labels},
    )
    return result if isinstance(result, list) else [result]


def remove_label(
    repo: str,
    issue_number: int,
    label: str,
) -> None:
    """Remove a label from an issue."""
    with contextlib.suppress(GhCliError):
        gh_api(
            f"/repos/{{owner}}/{{repo}}/issues/{issue_number}/labels/{label}",
            method="DELETE",
            repo=repo,
        )


def prefixed_label(prefix: str, name: str) -> str:
    """Build a label name with optional prefix.

    Example: prefixed_label("purser:", "type:task") → "purser:type:task"
             prefixed_label("", "type:task") → "type:task"
    """
    if prefix:
        return f"{prefix}{name}"
    return name
