"""Manage custom fields on GitHub Projects for purser integration."""

from __future__ import annotations

from typing import Any

from purser.gh.projects import create_field, get_project_fields

# Standard fields that purser expects on a GH Project
STANDARD_FIELDS = [
    ("Priority", "TEXT"),
    ("Type", "TEXT"),
    ("Blocked", "TEXT"),
    ("Blocking", "TEXT"),
]


def ensure_project_fields(project_id: str) -> dict[str, str]:
    """Ensure all standard purser fields exist on the project.

    Returns a dict mapping field name → field ID.
    """
    existing = get_project_fields(project_id)
    field_map: dict[str, str] = {}

    for field_data in existing:
        name = field_data.get("name", "")
        field_id = field_data.get("id", "")
        if name and field_id:
            field_map[name] = field_id

    # Create any missing fields
    for name, data_type in STANDARD_FIELDS:
        if name not in field_map:
            new_field = create_field(project_id, name, data_type)
            if new_field.get("id"):
                field_map[name] = new_field["id"]

    return field_map


def build_field_values(
    issue_type: str,
    priority: int,
    blocks: list[str] | None = None,
    blocked_by: list[str] | None = None,
) -> dict[str, Any]:
    """Build field value updates for a project item.

    Returns dict of field_name → value suitable for set_field_value.
    """
    priority_names = {
        0: "P0 Critical",
        1: "P1 High",
        2: "P2 Medium",
        3: "P3 Low",
        4: "P4 Backlog",
    }

    values: dict[str, Any] = {
        "Type": {"text": issue_type},
        "Priority": {"text": priority_names.get(priority, f"P{priority}")},
    }

    if blocks:
        values["Blocking"] = {"text": ", ".join(blocks)}
    if blocked_by:
        values["Blocked"] = {"text": ", ".join(blocked_by)}

    return values


def sync_item_fields(
    project_id: str,
    item_id: str,
    field_map: dict[str, str],
    issue_type: str,
    priority: int,
    blocks: list[str] | None = None,
    blocked_by: list[str] | None = None,
) -> None:
    """Sync all custom field values for a project item.

    Args:
        project_id: GH Project node ID.
        item_id: GH Project item ID.
        field_map: Mapping of field name → field ID.
        issue_type: Bead type (task, feature, etc).
        priority: Bead priority (0-4).
        blocks: List of issue refs this item blocks.
        blocked_by: List of issue refs blocking this item.
    """
    from purser.gh.projects import set_field_value

    values = build_field_values(issue_type, priority, blocks, blocked_by)
    for field_name, value in values.items():
        field_id = field_map.get(field_name)
        if field_id:
            set_field_value(project_id, item_id, field_id, value)
