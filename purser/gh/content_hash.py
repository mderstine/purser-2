"""Deterministic content hashing for bead change detection.

Computes a stable hash of the bead fields that matter for sync,
used to detect whether local or remote content has changed since
the last sync.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from purser.models import Issue


def compute_content_hash(issue: Issue) -> str:
    """Compute a deterministic SHA-256 hash of sync-relevant bead fields.

    Fields included: title, description, status, priority, type,
    assignee, labels (sorted), parent, dependencies (sorted).

    Returns a hex digest string.
    """
    deps = sorted(
        [{"type": d.type, "target_id": d.target_id} for d in issue.dependencies],
        key=lambda d: (d["type"], d["target_id"]),
    )

    payload = {
        "title": issue.title,
        "description": issue.description or "",
        "status": issue.status,
        "priority": issue.priority,
        "type": issue.type,
        "assignee": issue.assignee or "",
        "labels": sorted(issue.labels),
        "parent": issue.parent or "",
        "dependencies": deps,
    }

    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()
