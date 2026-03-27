"""Typed accessors for GitHub sync metadata stored in Issue.metadata.

All GH-related metadata is stored in the generic `issue.metadata` dict
under the `gh_` prefix. These helpers provide typed get/set access.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

# --- Keys ---

GH_ISSUE_NUMBER = "gh_issue_number"
GH_PROJECT_ITEM_ID = "gh_project_item_id"
GH_REPO = "gh_repo"
LAST_SYNCED_AT = "gh_last_synced_at"
SYNC_HASH = "gh_sync_hash"
OWNER = "gh_owner"
START_DATE = "gh_start_date"
END_DATE = "gh_end_date"
DUE_DATE = "gh_due_date"
ESTIMATED_EFFORT = "gh_estimated_effort"
ACTUAL_EFFORT = "gh_actual_effort"
MILESTONE = "gh_milestone"


# --- Getters ---


def get_str(meta: dict[str, Any], key: str) -> str | None:
    """Get a string value from metadata."""
    val = meta.get(key)
    return str(val) if val is not None else None


def get_int(meta: dict[str, Any], key: str) -> int | None:
    """Get an integer value from metadata."""
    val = meta.get(key)
    if val is None:
        return None
    return int(val)


def get_date(meta: dict[str, Any], key: str) -> date | None:
    """Get a date value from metadata (stored as ISO string)."""
    val = meta.get(key)
    if val is None:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))


def get_datetime(meta: dict[str, Any], key: str) -> datetime | None:
    """Get a datetime value from metadata (stored as ISO string)."""
    val = meta.get(key)
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(str(val))


# --- Setters ---


def set_str(meta: dict[str, Any], key: str, value: str | None) -> None:
    """Set a string value in metadata."""
    if value is None:
        meta.pop(key, None)
    else:
        meta[key] = value


def set_int(meta: dict[str, Any], key: str, value: int | None) -> None:
    """Set an integer value in metadata."""
    if value is None:
        meta.pop(key, None)
    else:
        meta[key] = value


def set_date(meta: dict[str, Any], key: str, value: date | None) -> None:
    """Set a date value in metadata (stored as ISO string)."""
    if value is None:
        meta.pop(key, None)
    else:
        meta[key] = value.isoformat()


def set_datetime(meta: dict[str, Any], key: str, value: datetime | None) -> None:
    """Set a datetime value in metadata (stored as ISO string)."""
    if value is None:
        meta.pop(key, None)
    else:
        meta[key] = value.isoformat()


# --- Convenience accessors for common fields ---


def get_gh_issue_number(meta: dict[str, Any]) -> int | None:
    return get_int(meta, GH_ISSUE_NUMBER)


def set_gh_issue_number(meta: dict[str, Any], num: int | None) -> None:
    set_int(meta, GH_ISSUE_NUMBER, num)


def get_gh_repo(meta: dict[str, Any]) -> str | None:
    return get_str(meta, GH_REPO)


def set_gh_repo(meta: dict[str, Any], repo: str | None) -> None:
    set_str(meta, GH_REPO, repo)


def get_gh_project_item_id(meta: dict[str, Any]) -> str | None:
    return get_str(meta, GH_PROJECT_ITEM_ID)


def set_gh_project_item_id(meta: dict[str, Any], item_id: str | None) -> None:
    set_str(meta, GH_PROJECT_ITEM_ID, item_id)


def get_last_synced_at(meta: dict[str, Any]) -> datetime | None:
    return get_datetime(meta, LAST_SYNCED_AT)


def set_last_synced_at(meta: dict[str, Any], dt: datetime | None) -> None:
    set_datetime(meta, LAST_SYNCED_AT, dt)


def get_sync_hash(meta: dict[str, Any]) -> str | None:
    return get_str(meta, SYNC_HASH)


def set_sync_hash(meta: dict[str, Any], h: str | None) -> None:
    set_str(meta, SYNC_HASH, h)


def get_owner(meta: dict[str, Any]) -> str | None:
    return get_str(meta, OWNER)


def set_owner(meta: dict[str, Any], owner: str | None) -> None:
    set_str(meta, OWNER, owner)


def get_due_date(meta: dict[str, Any]) -> date | None:
    return get_date(meta, DUE_DATE)


def set_due_date(meta: dict[str, Any], d: date | None) -> None:
    set_date(meta, DUE_DATE, d)


def get_estimated_effort(meta: dict[str, Any]) -> str | None:
    return get_str(meta, ESTIMATED_EFFORT)


def set_estimated_effort(meta: dict[str, Any], effort: str | None) -> None:
    set_str(meta, ESTIMATED_EFFORT, effort)


def get_actual_effort(meta: dict[str, Any]) -> str | None:
    return get_str(meta, ACTUAL_EFFORT)


def set_actual_effort(meta: dict[str, Any], effort: str | None) -> None:
    set_str(meta, ACTUAL_EFFORT, effort)
