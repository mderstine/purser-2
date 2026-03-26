"""Session manager for token storage and invalidation.

This module provides session management including token storage,
refresh token rotation, and session invalidation (logout).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from purser.auth.config import OAuthConfig  # noqa: TC001
from purser.auth.jwt_manager import JWTError, JWTManager, TokenInvalidError


@dataclass
class SessionInfo:
    """Active session information.

    Attributes:
        token_id: Refresh token record ID
        user_id: User ID
        created_at: Session creation time
        expires_at: Session expiration time
        ip_address: Client IP
        user_agent: Client user agent
        is_current: Whether this is the current session
    """

    token_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None
    is_current: bool = False


@dataclass
class TokenPair:
    """Access and refresh token pair.

    Attributes:
        access_token: Short-lived JWT access token
        refresh_token: Long-lived JWT refresh token
        token_type: Token type (Bearer)
        expires_in: Access token lifetime in seconds
    """

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900


class SessionError(Exception):
    """Exception raised for session-related errors."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class SessionRevokedError(SessionError):
    """Exception raised when a session has been revoked."""

    pass


class SessionManager:
    """Manager for user sessions and token storage.

    Handles refresh token storage, rotation, and session invalidation
    for secure authentication flows.
    """

    def __init__(
        self,
        config: OAuthConfig,
        jwt_manager: JWTManager | None = None,
        storage: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the session manager.

        Args:
            config: OAuth configuration
            jwt_manager: Optional JWT manager instance
            storage: Optional storage backend (dict for in-memory, or external)
        """
        self.config = config
        self.jwt_manager = jwt_manager or JWTManager(config)
        self._storage = storage or {}
        self._refresh_tokens: dict[str, dict[str, Any]] = {}
        self._revoked_tokens: set[str] = set()

    def create_session(
        self,
        user_id: str,
        email: str,
        is_verified: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> TokenPair:
        """Create a new session with access and refresh tokens.

        Args:
            user_id: Unique user identifier
            email: User email address
            is_verified: Whether the user's email is verified
            ip_address: Client IP address for audit
            user_agent: Client user agent for audit
            extra_claims: Additional claims to include in tokens

        Returns:
            TokenPair containing access and refresh tokens
        """
        # Create token pair using JWT manager
        tokens = self.jwt_manager.create_token_pair(
            user_id=user_id,
            email=email,
            is_verified=is_verified,
            extra_claims=extra_claims,
        )

        # Store refresh token hash for revocation support
        refresh_token = tokens["refresh_token"]
        token_hash = self._hash_token(refresh_token)
        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        self._refresh_tokens[token_hash] = {
            "id": token_id,
            "user_id": user_id,
            "token_hash": token_hash,
            "created_at": now.isoformat(),
            "expires_at": (now + self.config.refresh_token_expire_days * 24).isoformat(),
            "revoked_at": None,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        return TokenPair(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"],
        )

    def refresh_session(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> TokenPair:
        """Refresh a session by rotating the refresh token.

        Args:
            refresh_token: Current refresh token
            ip_address: Client IP address for audit
            user_agent: Client user agent for audit
            extra_claims: Additional claims for new tokens

        Returns:
            New TokenPair with rotated tokens

        Raises:
            SessionRevokedError: If the session has been revoked
            TokenInvalidError: If the token is invalid
        """
        # Check if token is revoked
        token_hash = self._hash_token(refresh_token)
        if token_hash in self._revoked_tokens:
            raise SessionRevokedError("Token has been revoked", "TOKEN_REVOKED")

        # Check if token exists in storage
        stored_token = self._refresh_tokens.get(token_hash)
        if stored_token and stored_token.get("revoked_at"):
            raise SessionRevokedError("Token has been revoked", "TOKEN_REVOKED")

        # Validate and rotate the token using JWT manager
        try:
            tokens = self.jwt_manager.rotate_refresh_token(
                refresh_token, extra_claims=extra_claims
            )
        except JWTError as e:
            raise TokenInvalidError(str(e)) from e

        # Revoke the old token (token rotation)
        self._revoke_token_by_hash(token_hash, revoke_in_storage=True)

        # Store the new refresh token
        new_refresh_token = tokens["refresh_token"]
        new_token_hash = self._hash_token(new_refresh_token)
        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        self._refresh_tokens[new_token_hash] = {
            "id": token_id,
            "user_id": self.jwt_manager.validate_refresh_token(new_refresh_token).get("user_id"),
            "token_hash": new_token_hash,
            "created_at": now.isoformat(),
            "expires_at": (now + self.config.refresh_token_expire_days * 24).isoformat(),
            "revoked_at": None,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        return TokenPair(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"],
        )

    def revoke_session(self, refresh_token: str, revoke_all: bool = False) -> dict[str, Any]:
        """Revoke a session (logout).

        Args:
            refresh_token: The refresh token to revoke
            revoke_all: If True, revoke all sessions for the user

        Returns:
            Dictionary with revoked session details

        Raises:
            TokenInvalidError: If the token cannot be validated
        """
        if revoke_all:
            # Get user_id from token
            try:
                payload = self.jwt_manager.validate_refresh_token(refresh_token)
                user_id = payload.get("user_id")
            except JWTError as err:
                raise TokenInvalidError("Invalid token") from err

            # Revoke all sessions for this user
            revoked_count = 0
            for token_hash, stored in list(self._refresh_tokens.items()):
                if stored.get("user_id") == user_id and not stored.get("revoked_at"):
                    self._revoke_token_by_hash(token_hash)
                    revoked_count += 1

            return {
                "revoked": True,
                "revoked_all": True,
                "user_id": user_id,
                "sessions_revoked": revoked_count,
            }
        else:
            # Revoke only this session
            token_hash = self._hash_token(refresh_token)
            self._revoke_token_by_hash(token_hash, revoke_in_storage=True)

            return {
                "revoked": True,
                "revoked_all": False,
                "token_hash": token_hash[:16] + "...",  # Truncated for security
            }

    def _revoke_token_by_hash(self, token_hash: str, revoke_in_storage: bool = False) -> None:
        """Revoke a token by its hash.

        Args:
            token_hash: SHA256 hash of the token
            revoke_in_storage: Also update the storage record
        """
        self._revoked_tokens.add(token_hash)

        if revoke_in_storage and token_hash in self._refresh_tokens:
            self._refresh_tokens[token_hash]["revoked_at"] = datetime.now(UTC).isoformat()

    def is_token_revoked(self, token: str) -> bool:
        """Check if a token has been revoked.

        Args:
            token: The token to check

        Returns:
            True if the token is revoked, False otherwise
        """
        token_hash = self._hash_token(token)
        return token_hash in self._revoked_tokens

    def get_active_sessions(self, user_id: str) -> list[SessionInfo]:
        """Get all active sessions for a user.

        Args:
            user_id: The user ID to query

        Returns:
            List of active SessionInfo objects
        """
        sessions: list[SessionInfo] = []
        now = datetime.now(UTC)

        for stored in self._refresh_tokens.values():
            if stored.get("user_id") != user_id:
                continue
            if stored.get("revoked_at"):
                continue

            # Check expiration
            expires_at_str = stored.get("expires_at")
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at < now:
                    continue

            sessions.append(
                SessionInfo(
                    token_id=uuid.UUID(stored.get("id", str(uuid.uuid4()))),
                    user_id=uuid.UUID(stored.get("user_id")),
                    created_at=datetime.fromisoformat(stored.get("created_at", "")),
                    expires_at=datetime.fromisoformat(stored.get("expires_at", "")),
                    ip_address=stored.get("ip_address"),
                    user_agent=stored.get("user_agent"),
                    is_current=False,
                )
            )

        return sessions

    def validate_access_token(self, token: str) -> dict[str, Any]:
        """Validate an access token.

        Args:
            token: The access token to validate

        Returns:
            Decoded token payload

        Raises:
            TokenInvalidError: If the token is invalid
        """
        return self.jwt_manager.validate_access_token(token)

    def validate_refresh_token(self, token: str) -> dict[str, Any]:
        """Validate a refresh token and check revocation status.

        Args:
            token: The refresh token to validate

        Returns:
            Decoded token payload

        Raises:
            SessionRevokedError: If the token has been revoked
            TokenInvalidError: If the token is invalid
        """
        if self.is_token_revoked(token):
            raise SessionRevokedError("Token has been revoked", "TOKEN_REVOKED")

        return self.jwt_manager.validate_refresh_token(token)

    @staticmethod
    def _hash_token(token: str) -> str:
        """Generate SHA256 hash of a token.

        Args:
            token: The raw token string

        Returns:
            SHA256 hex digest of the token
        """
        return hashlib.sha256(token.encode()).hexdigest()

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions from storage.

        Returns:
            Number of sessions removed
        """
        now = datetime.now(UTC)
        removed = 0

        for token_hash in list(self._refresh_tokens.keys()):
            stored = self._refresh_tokens[token_hash]
            expires_at_str = stored.get("expires_at")

            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at < now:
                    del self._refresh_tokens[token_hash]
                    removed += 1

        return removed
