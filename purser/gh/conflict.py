"""Three-way conflict detection and resolution for bidirectional sync.

Compares local content hash, remote content hash, and the stored
sync hash (from last successful sync) to classify changes.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

import click


class ChangeClass(Enum):
    """Classification of a sync entry's change state."""

    NO_CHANGE = "no-change"
    LOCAL_ONLY = "local-only"
    REMOTE_ONLY = "remote-only"
    CONFLICT = "conflict"


class Resolution(Enum):
    """How a conflict was resolved."""

    USE_LOCAL = "use-local"
    USE_REMOTE = "use-remote"
    SKIP = "skip"


def classify_change(
    local_hash: str,
    remote_hash: str,
    sync_hash: str | None,
) -> ChangeClass:
    """Classify a bead's change state using three-way comparison.

    Args:
        local_hash: Content hash of the local bead.
        remote_hash: Content hash of the remote GH issue.
        sync_hash: Content hash stored at last sync (None if never synced).

    Returns:
        ChangeClass indicating what changed.
    """
    if sync_hash is None:
        # Never synced before — if they match, no change; otherwise conflict
        if local_hash == remote_hash:
            return ChangeClass.NO_CHANGE
        return ChangeClass.CONFLICT

    local_changed = local_hash != sync_hash
    remote_changed = remote_hash != sync_hash

    if not local_changed and not remote_changed:
        return ChangeClass.NO_CHANGE
    if local_changed and not remote_changed:
        return ChangeClass.LOCAL_ONLY
    if not local_changed and remote_changed:
        return ChangeClass.REMOTE_ONLY
    return ChangeClass.CONFLICT


def resolve_conflict(
    bead_id: str,
    strategy: Literal["local-wins", "remote-wins", "prompt"],
    local_title: str = "",
    remote_title: str = "",
) -> Resolution:
    """Resolve a conflict using the configured strategy.

    Args:
        bead_id: The bead that has a conflict.
        strategy: Resolution strategy from config.
        local_title: Local bead title (for prompt display).
        remote_title: Remote issue title (for prompt display).

    Returns:
        Resolution indicating which side to use or to skip.
    """
    if strategy == "local-wins":
        return Resolution.USE_LOCAL
    if strategy == "remote-wins":
        return Resolution.USE_REMOTE

    # Prompt the user
    click.echo(f"\nConflict on {bead_id}:")
    click.echo(f"  Local:  {local_title}")
    click.echo(f"  Remote: {remote_title}")
    choice = click.prompt(
        "  Resolve",
        type=click.Choice(["local", "remote", "skip"]),
        default="skip",
    )
    if choice == "local":
        return Resolution.USE_LOCAL
    if choice == "remote":
        return Resolution.USE_REMOTE
    return Resolution.SKIP
