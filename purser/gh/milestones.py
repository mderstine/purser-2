"""GitHub Milestones API wrapper via gh CLI."""

from __future__ import annotations

from typing import Any

from purser.gh.cli import gh_api


def create_milestone(
    repo: str,
    title: str,
    description: str = "",
    due_on: str | None = None,
) -> dict[str, Any]:
    """Create a milestone on a repo."""
    payload: dict[str, Any] = {"title": title}
    if description:
        payload["description"] = description
    if due_on:
        payload["due_on"] = due_on  # ISO 8601 format

    result = gh_api(
        "/repos/{owner}/{repo}/milestones",
        method="POST",
        repo=repo,
        json_body=payload,
    )
    assert isinstance(result, dict)
    return result


def update_milestone(
    repo: str,
    milestone_number: int,
    *,
    title: str | None = None,
    description: str | None = None,
    state: str | None = None,
    due_on: str | None = None,
) -> dict[str, Any]:
    """Update a milestone."""
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if state is not None:
        payload["state"] = state
    if due_on is not None:
        payload["due_on"] = due_on

    result = gh_api(
        f"/repos/{{owner}}/{{repo}}/milestones/{milestone_number}",
        method="PATCH",
        repo=repo,
        json_body=payload,
    )
    assert isinstance(result, dict)
    return result


def list_milestones(
    repo: str,
    state: str = "open",
) -> list[dict[str, Any]]:
    """List milestones for a repo."""
    result = gh_api(
        "/repos/{owner}/{repo}/milestones",
        repo=repo,
        fields={"state": state, "per_page": "100"},
    )
    return result if isinstance(result, list) else [result]


def find_milestone_by_title(repo: str, title: str) -> dict[str, Any] | None:
    """Find a milestone by title. Returns the milestone dict or None."""
    milestones = list_milestones(repo, state="open")
    for ms in milestones:
        if ms.get("title") == title:
            return ms
    # Also check closed milestones
    milestones = list_milestones(repo, state="closed")
    for ms in milestones:
        if ms.get("title") == title:
            return ms
    return None


def assign_issue_to_milestone(
    repo: str,
    issue_number: int,
    milestone_number: int,
) -> dict[str, Any]:
    """Assign an issue to a milestone."""
    result = gh_api(
        f"/repos/{{owner}}/{{repo}}/issues/{issue_number}",
        method="PATCH",
        repo=repo,
        json_body={"milestone": milestone_number},
    )
    assert isinstance(result, dict)
    return result
