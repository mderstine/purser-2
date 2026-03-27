"""Map purser hierarchy levels to GitHub constructs.

Objective → GH Project
Epic → Milestone + epic: label
Feature → GH Issue (type:feature)
Task → GH Issue (type:task)
Sub-task → Task list in parent issue body
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from purser.gh.labels import ensure_label, prefixed_label

if TYPE_CHECKING:
    from purser.models import GitHubConfig, Issue


def ensure_type_labels(repo: str, prefix: str) -> None:
    """Ensure all standard type and priority labels exist on the repo."""
    type_labels = [
        ("type:task", "0e8a16", "Purser task"),
        ("type:feature", "1d76db", "Purser feature"),
        ("type:epic", "d93f0b", "Purser epic"),
        ("type:bug", "b60205", "Purser bug"),
        ("type:chore", "c5def5", "Purser chore"),
    ]
    priority_labels = [
        ("priority:critical", "b60205", "P0 Critical"),
        ("priority:high", "d93f0b", "P1 High"),
        ("priority:medium", "fbca04", "P2 Medium"),
        ("priority:low", "0e8a16", "P3 Low"),
        ("priority:backlog", "c5def5", "P4 Backlog"),
    ]
    for name, color, desc in [*type_labels, *priority_labels]:
        ensure_label(repo, prefixed_label(prefix, name), color=color, description=desc)


def map_epic_to_milestone(
    issue: Issue,
    repo: str,
    gh_config: GitHubConfig,
) -> dict[str, Any]:
    """Map an epic bead to a GH Milestone.

    Returns milestone data dict (with 'number' for assignment).
    Creates the milestone if it doesn't exist.
    """
    from purser.gh.milestones import create_milestone, find_milestone_by_title

    title = issue.title.removeprefix("Epic: ").strip()
    existing = find_milestone_by_title(repo, title)
    if existing:
        return existing

    description = issue.description or ""
    return create_milestone(repo, title, description=description)


def build_subtask_list(
    children: list[Issue],
) -> str:
    """Build a GitHub task list from child beads.

    Returns markdown like:
    - [ ] Sub-task title
    - [x] Completed sub-task
    """
    lines = []
    for child in children:
        checked = "x" if child.status == "closed" else " "
        lines.append(f"- [{checked}] {child.title}")
    return "\n".join(lines)
