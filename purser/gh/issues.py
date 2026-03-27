"""GitHub Issues API wrapper via gh CLI."""

from __future__ import annotations

from typing import Any

from purser.gh.cli import gh_api


def create_issue(
    repo: str,
    title: str,
    body: str = "",
    labels: list[str] | None = None,
    assignee: str | None = None,
    milestone: int | None = None,
) -> dict[str, Any]:
    """Create a GitHub issue."""
    fields: dict[str, Any] = {"title": title}
    if body:
        fields["body"] = body
    if labels:
        fields["labels"] = ",".join(labels)
    if assignee:
        fields["assignee"] = assignee
    if milestone is not None:
        fields["milestone"] = str(milestone)

    result = gh_api(
        "/repos/{owner}/{repo}/issues",
        method="POST",
        repo=repo,
        json_body=fields,
    )
    assert isinstance(result, dict)
    return result


def update_issue(
    repo: str,
    issue_number: int,
    *,
    title: str | None = None,
    body: str | None = None,
    state: str | None = None,
    labels: list[str] | None = None,
    assignee: str | None = None,
    milestone: int | None = None,
) -> dict[str, Any]:
    """Update a GitHub issue."""
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if state is not None:
        payload["state"] = state
    if labels is not None:
        payload["labels"] = labels
    if assignee is not None:
        payload["assignee"] = assignee
    if milestone is not None:
        payload["milestone"] = milestone

    result = gh_api(
        f"/repos/{{owner}}/{{repo}}/issues/{issue_number}",
        method="PATCH",
        repo=repo,
        json_body=payload,
    )
    assert isinstance(result, dict)
    return result


def get_issue(repo: str, issue_number: int) -> dict[str, Any]:
    """Get a GitHub issue by number."""
    result = gh_api(
        f"/repos/{{owner}}/{{repo}}/issues/{issue_number}",
        repo=repo,
    )
    assert isinstance(result, dict)
    return result


def list_issues(
    repo: str,
    *,
    state: str = "open",
    labels: str | None = None,
    milestone: str | None = None,
    per_page: int = 100,
) -> list[dict[str, Any]]:
    """List GitHub issues."""
    fields: dict[str, Any] = {"state": state, "per_page": str(per_page)}
    if labels:
        fields["labels"] = labels
    if milestone:
        fields["milestone"] = milestone

    result = gh_api(
        "/repos/{owner}/{repo}/issues",
        repo=repo,
        fields=fields,
        paginate=True,
    )
    return result if isinstance(result, list) else [result]


def close_issue(repo: str, issue_number: int) -> dict[str, Any]:
    """Close a GitHub issue."""
    return update_issue(repo, issue_number, state="closed")
