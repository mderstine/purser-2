"""DuckDB-backed sync state store for GitHub integration.

Tracks the mapping between local bead IDs and GitHub issue numbers,
along with content hashes for conflict detection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import duckdb
from pydantic import BaseModel

if TYPE_CHECKING:
    from pathlib import Path

# Sync status values
SYNCED = "synced"
LOCAL_DIRTY = "local-dirty"
REMOTE_DIRTY = "remote-dirty"
CONFLICT = "conflict"
UNLINKED = "unlinked"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS gh_sync_map (
    bead_id       TEXT PRIMARY KEY,
    gh_repo       TEXT NOT NULL,
    gh_issue_num  INTEGER,
    gh_project_id TEXT,
    content_hash  TEXT,
    last_synced   TIMESTAMP,
    sync_status   TEXT DEFAULT 'unlinked'
)
"""


class SyncState(BaseModel):
    """Represents the sync state of a single bead."""

    bead_id: str
    gh_repo: str
    gh_issue_num: int | None = None
    gh_project_id: str | None = None
    content_hash: str | None = None
    last_synced: datetime | None = None
    sync_status: str = UNLINKED


class SyncStore:
    """Manages the gh_sync_map table in DuckDB."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = str(db_path)
        self.conn = duckdb.connect(self.db_path)
        self.conn.execute(_CREATE_TABLE)

    def upsert(self, state: SyncState) -> None:
        """Insert or update a sync state entry."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO gh_sync_map
                (bead_id, gh_repo, gh_issue_num, gh_project_id, content_hash, last_synced, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                state.bead_id,
                state.gh_repo,
                state.gh_issue_num,
                state.gh_project_id,
                state.content_hash,
                state.last_synced,
                state.sync_status,
            ],
        )

    def get(self, bead_id: str) -> SyncState | None:
        """Get sync state for a bead."""
        row = self.conn.execute(
            "SELECT bead_id, gh_repo, gh_issue_num, gh_project_id, content_hash, last_synced, sync_status "
            "FROM gh_sync_map WHERE bead_id = ?",
            [bead_id],
        ).fetchone()
        if row is None:
            return None
        return SyncState(
            bead_id=row[0],
            gh_repo=row[1],
            gh_issue_num=row[2],
            gh_project_id=row[3],
            content_hash=row[4],
            last_synced=row[5],
            sync_status=row[6],
        )

    def list_by_status(self, status: str) -> list[SyncState]:
        """List all sync entries with a given status."""
        rows = self.conn.execute(
            "SELECT bead_id, gh_repo, gh_issue_num, gh_project_id, content_hash, last_synced, sync_status "
            "FROM gh_sync_map WHERE sync_status = ?",
            [status],
        ).fetchall()
        return [
            SyncState(
                bead_id=r[0],
                gh_repo=r[1],
                gh_issue_num=r[2],
                gh_project_id=r[3],
                content_hash=r[4],
                last_synced=r[5],
                sync_status=r[6],
            )
            for r in rows
        ]

    def list_all(self) -> list[SyncState]:
        """List all sync entries."""
        rows = self.conn.execute(
            "SELECT bead_id, gh_repo, gh_issue_num, gh_project_id, content_hash, last_synced, sync_status "
            "FROM gh_sync_map"
        ).fetchall()
        return [
            SyncState(
                bead_id=r[0],
                gh_repo=r[1],
                gh_issue_num=r[2],
                gh_project_id=r[3],
                content_hash=r[4],
                last_synced=r[5],
                sync_status=r[6],
            )
            for r in rows
        ]

    def delete(self, bead_id: str) -> None:
        """Remove a sync state entry."""
        self.conn.execute("DELETE FROM gh_sync_map WHERE bead_id = ?", [bead_id])

    def mark_synced(self, bead_id: str, content_hash: str) -> None:
        """Mark a bead as synced with the given content hash."""
        now = datetime.now(UTC)
        self.conn.execute(
            "UPDATE gh_sync_map SET sync_status = ?, content_hash = ?, last_synced = ? WHERE bead_id = ?",
            [SYNCED, content_hash, now, bead_id],
        )

    def mark_dirty(self, bead_id: str, side: str) -> None:
        """Mark a bead as dirty (side = 'local-dirty' or 'remote-dirty')."""
        self.conn.execute(
            "UPDATE gh_sync_map SET sync_status = ? WHERE bead_id = ?",
            [side, bead_id],
        )

    def mark_conflict(self, bead_id: str) -> None:
        """Mark a bead as having a conflict."""
        self.conn.execute(
            "UPDATE gh_sync_map SET sync_status = ? WHERE bead_id = ?",
            [CONFLICT, bead_id],
        )

    def summary(self) -> dict[str, int]:
        """Get count of entries by sync status."""
        rows = self.conn.execute(
            "SELECT sync_status, COUNT(*) FROM gh_sync_map GROUP BY sync_status"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def last_sync_time(self) -> datetime | None:
        """Get the most recent sync timestamp."""
        row = self.conn.execute("SELECT MAX(last_synced) FROM gh_sync_map").fetchone()
        return row[0] if row and row[0] else None

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
