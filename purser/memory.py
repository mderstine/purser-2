"""DuckDB-backed session memory store."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from pydantic import BaseModel


class MemoryEntry(BaseModel):
    key: str
    value: str
    namespace: str = "default"
    stored_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class MemoryStore:
    """Session memory backed by DuckDB with full-text search."""

    def __init__(self, db_path: Path | str = ".purser/memory.duckdb"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT,
                value TEXT,
                namespace TEXT DEFAULT 'default',
                metadata JSON,
                stored_at TIMESTAMP DEFAULT current_timestamp,
                PRIMARY KEY (key, namespace)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT,
                seq INTEGER,
                role TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT current_timestamp
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS contexts (
                issue_id TEXT PRIMARY KEY,
                context TEXT,
                updated_at TIMESTAMP DEFAULT current_timestamp
            )
        """)
        # Create FTS index on memories if not exists
        with contextlib.suppress(duckdb.Error):
            self.conn.execute("""
                PRAGMA create_fts_index('memories', 'key', 'value',
                    overwrite=1)
            """)

    def store(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store or update a key-value pair."""
        now = datetime.now(UTC)
        import json as _json

        meta_json = _json.dumps(metadata) if metadata else None
        self.conn.execute(
            """
            INSERT OR REPLACE INTO memories (key, value, namespace, metadata, stored_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [key, value, namespace, meta_json, now],
        )

    def get(self, key: str, namespace: str = "default") -> str | None:
        """Retrieve a value by key."""
        result = self.conn.execute(
            "SELECT value FROM memories WHERE key = ? AND namespace = ?",
            [key, namespace],
        ).fetchone()
        return result[0] if result else None

    def query(self, text: str, limit: int = 10) -> list[MemoryEntry]:
        """Search memories by text (substring match, FTS when available)."""
        try:
            rows = self.conn.execute(
                """
                SELECT key, value, namespace, stored_at, metadata
                FROM memories
                WHERE fts_main_memories.match_bm25(key, ?, value, ?) IS NOT NULL
                ORDER BY fts_main_memories.match_bm25(key, ?, value, ?) DESC
                LIMIT ?
                """,
                [text, text, text, text, limit],
            ).fetchall()
        except duckdb.Error:
            # Fallback to LIKE search
            rows = self.conn.execute(
                """
                SELECT key, value, namespace, stored_at, metadata
                FROM memories
                WHERE value ILIKE ? OR key ILIKE ?
                ORDER BY stored_at DESC
                LIMIT ?
                """,
                [f"%{text}%", f"%{text}%", limit],
            ).fetchall()

        return [
            MemoryEntry(
                key=r[0],
                value=r[1],
                namespace=r[2],
                stored_at=r[3],
                metadata=r[4],
            )
            for r in rows
        ]

    def store_conversation(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Append a message to conversation history."""
        row = self.conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM conversations WHERE session_id = ?",
            [session_id],
        ).fetchone()
        seq = row[0] if row else 1
        self.conn.execute(
            """
            INSERT INTO conversations (session_id, seq, role, content)
            VALUES (?, ?, ?, ?)
            """,
            [session_id, seq, role, content],
        )

    def get_conversation(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[dict[str, str]]:
        """Get recent conversation messages."""
        rows = self.conn.execute(
            """
            SELECT role, content FROM conversations
            WHERE session_id = ?
            ORDER BY seq DESC LIMIT ?
            """,
            [session_id, limit],
        ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def store_context(self, issue_id: str, context: str) -> None:
        """Store execution context for an issue."""
        now = datetime.now(UTC)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO contexts (issue_id, context, updated_at)
            VALUES (?, ?, ?)
            """,
            [issue_id, context, now],
        )

    def get_context(self, issue_id: str) -> str | None:
        """Retrieve context for an issue."""
        result = self.conn.execute(
            "SELECT context FROM contexts WHERE issue_id = ?",
            [issue_id],
        ).fetchone()
        return result[0] if result else None

    def flush(self) -> None:
        """Force WAL checkpoint."""
        with contextlib.suppress(duckdb.Error):
            self.conn.execute("CHECKPOINT")

    def close(self) -> None:
        """Close the database connection."""
        self.flush()
        self.conn.close()
