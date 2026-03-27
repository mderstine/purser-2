"""Serialize beads to GitHub Issue payloads and back.

Handles the conversion between purser Issue models and GitHub API
JSON structures, including label mapping, priority encoding, and
dependency footer generation/parsing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from purser.gh.dep_footer import DepFooter, render_dep_footer, strip_dep_footer
from purser.gh.labels import prefixed_label

if TYPE_CHECKING:
    from purser.gh.sync_store import SyncStore
    from purser.models import GitHubConfig, Issue

# Priority mapping: purser int → label name
PRIORITY_LABELS = {
    0: "priority:critical",
    1: "priority:high",
    2: "priority:medium",
    3: "priority:low",
    4: "priority:backlog",
}
PRIORITY_FROM_LABEL = {v: k for k, v in PRIORITY_LABELS.items()}

# Type mapping
TYPE_LABELS = {
    "task": "type:task",
    "feature": "type:feature",
    "epic": "type:epic",
    "bug": "type:bug",
    "chore": "type:chore",
}
TYPE_FROM_LABEL = {v: k for k, v in TYPE_LABELS.items()}


def bead_to_gh_payload(
    issue: Issue,
    gh_config: GitHubConfig,
    sync_store: SyncStore | None = None,
) -> dict[str, Any]:
    """Convert a purser Issue to a GitHub Issue create/update payload.

    Returns a dict suitable for passing to gh_api as json_body.
    """
    prefix = gh_config.label_prefix

    # Build labels
    labels: list[str] = []
    if issue.type in TYPE_LABELS:
        labels.append(prefixed_label(prefix, TYPE_LABELS[issue.type]))
    if issue.priority in PRIORITY_LABELS:
        labels.append(prefixed_label(prefix, PRIORITY_LABELS[issue.priority]))
    for label in issue.labels:
        labels.append(prefixed_label(prefix, label))

    # Build body with description + dependency footer
    body = issue.description or ""
    deps = _build_dep_footer(issue, sync_store)
    body += render_dep_footer(deps)

    # Map assignee via username_map
    assignee = issue.assignee
    if assignee and gh_config.username_map:
        assignee = gh_config.username_map.get(assignee, assignee)

    payload: dict[str, Any] = {
        "title": issue.title,
        "body": body,
        "labels": labels,
    }
    if assignee:
        payload["assignee"] = assignee
    if issue.status == "closed":
        payload["state"] = "closed"

    return payload


def gh_issue_to_bead_fields(
    gh_issue: dict[str, Any],
    gh_config: GitHubConfig,
) -> dict[str, Any]:
    """Convert a GitHub Issue JSON to a dict of bead-compatible fields.

    Returns a dict that can be used with bd update or Issue model construction.
    """
    prefix = gh_config.label_prefix
    gh_labels = [
        lbl["name"] if isinstance(lbl, dict) else lbl for lbl in gh_issue.get("labels", [])
    ]

    # Extract type from labels
    issue_type = "task"
    for lbl in gh_labels:
        unprefixed = lbl.removeprefix(prefix) if prefix else lbl
        if unprefixed in TYPE_FROM_LABEL:
            issue_type = TYPE_FROM_LABEL[unprefixed]
            break

    # Extract priority from labels
    priority = 2  # default medium
    for lbl in gh_labels:
        unprefixed = lbl.removeprefix(prefix) if prefix else lbl
        if unprefixed in PRIORITY_FROM_LABEL:
            priority = PRIORITY_FROM_LABEL[unprefixed]
            break

    # Filter out type/priority labels to get "pure" labels
    pure_labels = []
    for lbl in gh_labels:
        unprefixed = lbl.removeprefix(prefix) if prefix else lbl
        if unprefixed not in TYPE_FROM_LABEL and unprefixed not in PRIORITY_FROM_LABEL:
            pure_labels.append(unprefixed)

    # Parse body for description (without dep footer)
    body = gh_issue.get("body", "") or ""
    description = strip_dep_footer(body)

    # Map assignee back
    assignee = None
    if gh_issue.get("assignee"):
        gh_username = gh_issue["assignee"]["login"]
        # Reverse lookup in username_map
        reverse_map = {v: k for k, v in gh_config.username_map.items()}
        assignee = reverse_map.get(gh_username, gh_username)

    # Map status
    status = "open"
    if gh_issue.get("state") == "closed":
        status = "closed"

    return {
        "title": gh_issue.get("title", ""),
        "description": description,
        "type": issue_type,
        "status": status,
        "priority": priority,
        "assignee": assignee,
        "labels": pure_labels,
    }


def _build_dep_footer(
    issue: Issue,
    sync_store: SyncStore | None,
) -> DepFooter:
    """Build a DepFooter from an issue's dependencies.

    Translates bead IDs to GH issue numbers using the sync store.
    """
    footer = DepFooter()

    if not sync_store:
        return footer

    # Parent
    if issue.parent:
        parent_state = sync_store.get(issue.parent)
        if parent_state and parent_state.gh_issue_num:
            footer.parent = parent_state.gh_issue_num

    # Dependencies
    for dep in issue.dependencies:
        target_state = sync_store.get(dep.target_id)
        if not target_state or not target_state.gh_issue_num:
            continue
        num = target_state.gh_issue_num
        if dep.type == "blocks":
            footer.blocks.append(num)
        elif dep.type == "relates-to":
            footer.related.append(num)
        elif dep.type == "discovered-from":
            footer.discovered_from.append(num)

    return footer
