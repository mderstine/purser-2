"""Database repository for authentication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import duckdb

from purser.auth.models import OAuthAccount, RefreshToken, User


class AuthRepository:
    """Repository for authentication data using DuckDB."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize repository.

        Args:
            db_path: Path to DuckDB database. If None, uses in-memory.
        """
        if db_path is None:
            self.conn = duckdb.connect(":memory:")
        else:
            self.conn = duckdb.connect(str(db_path))
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        # Users table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255),
                is_verified BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)

        # OAuth accounts table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_accounts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider VARCHAR(50) NOT NULL,
                provider_user_id VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                access_token_encrypted TEXT,
                refresh_token_encrypted TEXT,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, provider_user_id)
            )
        """)

        # Refresh tokens table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash VARCHAR(64) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked_at TIMESTAMP,
                ip_address VARCHAR(45),
                user_agent TEXT
            )
        """)

        # Rate limiting table (in-memory)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                key VARCHAR(255) PRIMARY KEY,
                endpoint VARCHAR(255) NOT NULL,
                count INTEGER DEFAULT 1,
                window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_oauth_user ON oauth_accounts(user_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_refresh_hash ON refresh_tokens(token_hash)"
        )

    # User operations

    def create_user(self, email: str, password_hash: str) -> User:
        """Create a new user."""
        query = """
            INSERT INTO users (email, password_hash)
            VALUES ($1, $2)
            RETURNING id, email, password_hash, is_verified, is_active,
                      created_at, updated_at, last_login
        """
        result = self.conn.execute(query, [email, password_hash]).fetchone()
        if result is None:
            raise ValueError("Failed to create user")
        return self._row_to_user(result)

    def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        query = """
            SELECT id, email, password_hash, is_verified, is_active,
                   created_at, updated_at, last_login
            FROM users WHERE id = $1
        """
        result = self.conn.execute(query, [str(user_id)]).fetchone()
        return self._row_to_user(result) if result else None

    def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        query = """
            SELECT id, email, password_hash, is_verified, is_active,
                   created_at, updated_at, last_login
            FROM users WHERE email = $1
        """
        result = self.conn.execute(query, [email.lower()]).fetchone()
        return self._row_to_user(result) if result else None

    def update_user(self, user_id: UUID, **kwargs: Any) -> User | None:
        """Update user fields."""
        allowed_fields = ["email", "password_hash", "is_verified", "is_active"]
        updates = []
        values = []

        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ${len(values) + 2}")
                values.append(value)

        if not updates:
            return self.get_user_by_id(user_id)

        values.append(str(user_id))
        query = f"""
            UPDATE users
            SET {", ".join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            RETURNING id, email, password_hash, is_verified, is_active,
                      created_at, updated_at, last_login
        """
        result = self.conn.execute(query, values).fetchone()
        return self._row_to_user(result) if result else None

    def update_last_login(self, user_id: UUID) -> None:
        """Update user's last login time."""
        query = """
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
        """
        self.conn.execute(query, [str(user_id)])

    def delete_user(self, user_id: UUID) -> bool:
        """Delete user by ID."""
        query = "DELETE FROM users WHERE id = $1"
        self.conn.execute(query, [str(user_id)])
        return True

    def _row_to_user(self, row: tuple[Any, ...]) -> User:
        """Convert database row to User model."""
        return User(
            id=UUID(str(row[0])),
            email=str(row[1]),
            password_hash=str(row[2]) if row[2] else None,
            is_verified=bool(row[3]),
            is_active=bool(row[4]),
            created_at=row[5],
            updated_at=row[6],
            last_login=row[7],
        )

    # OAuth operations

    def create_oauth_account(self, account: OAuthAccount) -> OAuthAccount:
        """Create or update OAuth account."""
        query = """
            INSERT INTO oauth_accounts (
                user_id, provider, provider_user_id, email,
                access_token_encrypted, refresh_token_encrypted, expires_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (provider, provider_user_id) DO UPDATE SET
                email = EXCLUDED.email,
                access_token_encrypted = EXCLUDED.access_token_encrypted,
                refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                expires_at = EXCLUDED.expires_at,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id, user_id, provider, provider_user_id, email,
                      access_token_encrypted, refresh_token_encrypted,
                      expires_at, created_at, updated_at
        """
        result = self.conn.execute(
            query,
            [
                str(account.user_id),
                account.provider,
                account.provider_user_id,
                account.email,
                account.access_token_encrypted,
                account.refresh_token_encrypted,
                account.expires_at,
            ],
        ).fetchone()
        if result is None:
            raise ValueError("Failed to create OAuth account")
        return self._row_to_oauth_account(result)

    def get_oauth_account(self, provider: str, provider_user_id: str) -> OAuthAccount | None:
        """Get OAuth account by provider and user ID."""
        query = """
            SELECT id, user_id, provider, provider_user_id, email,
                   access_token_encrypted, refresh_token_encrypted,
                   expires_at, created_at, updated_at
            FROM oauth_accounts
            WHERE provider = $1 AND provider_user_id = $2
        """
        result = self.conn.execute(query, [provider, provider_user_id]).fetchone()
        return self._row_to_oauth_account(result) if result else None

    def _row_to_oauth_account(self, row: tuple[Any, ...]) -> OAuthAccount:
        """Convert database row to OAuthAccount model."""
        return OAuthAccount(
            id=UUID(str(row[0])),
            user_id=UUID(str(row[1])),
            provider=str(row[2]),
            provider_user_id=str(row[3]),
            email=str(row[4]) if row[4] else None,
            access_token_encrypted=str(row[5]) if row[5] else None,
            refresh_token_encrypted=str(row[6]) if row[6] else None,
            expires_at=row[7],
            created_at=row[8],
            updated_at=row[9],
        )

    # Refresh token operations

    def create_refresh_token(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> RefreshToken:
        """Create a refresh token."""
        query = """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at, ip_address, user_agent)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, user_id, token_hash, expires_at, created_at, revoked_at, ip_address, user_agent
        """
        result = self.conn.execute(
            query, [str(user_id), token_hash, expires_at, ip_address, user_agent]
        ).fetchone()
        if result is None:
            raise ValueError("Failed to create refresh token")
        return self._row_to_refresh_token(result)

    def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        """Get refresh token by hash."""
        query = """
            SELECT id, user_id, token_hash, expires_at, created_at, revoked_at, ip_address, user_agent
            FROM refresh_tokens WHERE token_hash = $1
        """
        result = self.conn.execute(query, [token_hash]).fetchone()
        return self._row_to_refresh_token(result) if result else None

    def revoke_refresh_token(self, token_hash: str) -> bool:
        """Revoke a refresh token."""
        query = """
            UPDATE refresh_tokens
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE token_hash = $1 AND revoked_at IS NULL
        """
        self.conn.execute(query, [token_hash])
        return True

    def revoke_all_user_tokens(self, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user."""
        query = """
            UPDATE refresh_tokens
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE user_id = $1 AND revoked_at IS NULL
        """
        self.conn.execute(query, [str(user_id)])
        return 0

    def _row_to_refresh_token(self, row: tuple[Any, ...]) -> RefreshToken:
        """Convert database row to RefreshToken model."""
        return RefreshToken(
            id=UUID(str(row[0])),
            user_id=UUID(str(row[1])),
            token_hash=str(row[2]),
            expires_at=row[3],
            created_at=row[4],
            revoked_at=row[5],
            ip_address=str(row[6]) if row[6] else None,
            user_agent=str(row[7]) if row[7] else None,
        )

    # Rate limiting

    def check_rate_limit(
        self, key: str, endpoint: str, max_requests: int, window_minutes: int
    ) -> tuple[bool, int]:
        """Check if request is within rate limit.

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        now = datetime.now(UTC)
        window_start = now - timedelta(minutes=window_minutes)

        # Clean old entries and get current count
        self.conn.execute("DELETE FROM rate_limits WHERE window_start < $1", [window_start])

        # Get or create entry
        existing = self.conn.execute(
            "SELECT count FROM rate_limits WHERE key = $1", [key]
        ).fetchone()

        if existing is None:
            self.conn.execute(
                "INSERT INTO rate_limits (key, endpoint, count, window_start) VALUES ($1, $2, 1, $3)",
                [key, endpoint, now],
            )
            return True, max_requests - 1

        count = existing[0]
        if count >= max_requests:
            return False, 0

        self.conn.execute(
            "UPDATE rate_limits SET count = count + 1 WHERE key = $1",
            [key],
        )
        return True, max_requests - count - 1

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __enter__(self) -> AuthRepository:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
