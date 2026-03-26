"""Authentication service for email/password authentication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar
from uuid import UUID

from purser.auth.models import TokenResponse, UserCreate, UserLogin, UserResponse
from purser.auth.repository import AuthRepository
from purser.auth.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    create_verification_token,
    decode_token,
    get_token_hash,
    hash_password,
    verify_password,
)


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class RateLimitExceededError(AuthenticationError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT_EXCEEDED")


class AuthService:
    """Service for handling authentication operations."""

    # Rate limit configuration
    RATE_LIMITS: ClassVar[dict[str, tuple[int, int]]] = {
        "register": (5, 15),  # 5 requests per 15 minutes
        "login": (10, 15),  # 10 requests per 15 minutes
        "forgot_password": (3, 60),  # 3 requests per hour
        "reset_password": (10, 15),  # 10 requests per 15 minutes
        "verify_email": (10, 15),  # 10 requests per 15 minutes
        "resend_verification": (3, 15),  # 3 requests per 15 minutes
    }

    def __init__(self, repository: AuthRepository | None = None) -> None:
        """Initialize the authentication service.

        Args:
            repository: Optional repository instance. Creates in-memory if not provided.
        """
        self.repo = repository or AuthRepository()

    def _check_rate_limit(self, key: str, endpoint: str) -> None:
        """Check if request is within rate limit."""
        if endpoint not in self.RATE_LIMITS:
            return

        max_requests, window_minutes = self.RATE_LIMITS[endpoint]
        allowed, _ = self.repo.check_rate_limit(key, endpoint, max_requests, window_minutes)

        if not allowed:
            raise RateLimitExceededError()

    def register_user(
        self,
        user_data: UserCreate,
        ip_address: str | None = None,
    ) -> tuple[UserResponse, str]:
        """Register a new user."""
        rate_key = ip_address or user_data.email
        self._check_rate_limit(rate_key, "register")

        # Check if email exists
        existing = self.repo.get_user_by_email(user_data.email)
        if existing:
            raise AuthenticationError("Email already registered", "EMAIL_EXISTS")

        # Hash password
        password_hash = hash_password(user_data.password)

        # Create user
        user = self.repo.create_user(
            email=user_data.email.lower(),
            password_hash=password_hash,
        )

        # Generate verification token
        verification_token = create_verification_token(user.id, user.email)

        return (
            UserResponse(
                id=user.id,
                email=user.email,
                is_verified=user.is_verified,
                is_active=user.is_active,
                created_at=user.created_at,
                last_login=user.last_login,
            ),
            verification_token,
        )

    def verify_email(self, token: str, ip_address: str | None = None) -> UserResponse:
        """Verify user email."""
        rate_key = ip_address or "verify"
        self._check_rate_limit(rate_key, "verify_email")

        # Decode and validate token
        payload = decode_token(token)
        if payload is None:
            raise AuthenticationError("Invalid or expired token", "INVALID_TOKEN")

        if payload.get("type") != "verification":
            raise AuthenticationError("Invalid token type", "INVALID_TOKEN")

        user_id = UUID(payload["sub"])

        # Update user
        user = self.repo.update_user(user_id, is_verified=True)
        if user is None:
            raise AuthenticationError("User not found", "USER_NOT_FOUND")

        return UserResponse(
            id=user.id,
            email=user.email,
            is_verified=user.is_verified,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login,
        )

    def resend_verification(self, email: str, ip_address: str | None = None) -> str | None:
        """Resend verification email."""
        rate_key = ip_address or email
        self._check_rate_limit(rate_key, "resend_verification")

        user = self.repo.get_user_by_email(email)
        if user is None or user.is_verified:
            return None  # Don't reveal if user exists

        return create_verification_token(user.id, user.email)

    def login(
        self,
        login_data: UserLogin,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Authenticate user and issue tokens."""
        rate_key = ip_address or login_data.email
        self._check_rate_limit(rate_key, "login")

        # Get user
        user = self.repo.get_user_by_email(login_data.email)
        if user is None:
            raise AuthenticationError("Invalid credentials", "INVALID_CREDENTIALS")

        # Check if user is active
        if not user.is_active:
            raise AuthenticationError("Account disabled", "ACCOUNT_DISABLED")

        # Check password
        if not user.password_hash:
            raise AuthenticationError("Invalid credentials", "INVALID_CREDENTIALS")

        if not verify_password(login_data.password, user.password_hash):
            raise AuthenticationError("Invalid credentials", "INVALID_CREDENTIALS")

        # Check if email is verified
        if not user.is_verified:
            raise AuthenticationError("Email not verified", "EMAIL_NOT_VERIFIED")

        # Update last login
        self.repo.update_last_login(user.id)

        # Create tokens
        access_token = create_access_token(user.id, user.email, user.is_verified)
        refresh_token, token_hash = create_refresh_token(user.id)

        # Store refresh token
        expires_at = datetime.now(UTC) + timedelta(days=7)
        self.repo.create_refresh_token(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=900,  # 15 minutes
        )

    def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token."""
        # Validate token
        payload = decode_token(refresh_token)
        if payload is None:
            raise AuthenticationError("Invalid or expired token", "INVALID_TOKEN")

        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type", "INVALID_TOKEN")

        user_id = UUID(payload["sub"])

        # Check if token is revoked
        token_hash = get_token_hash(refresh_token)
        stored_token = self.repo.get_refresh_token(token_hash)
        if stored_token is None or stored_token.revoked_at is not None:
            raise AuthenticationError("Token revoked", "TOKEN_REVOKED")

        # Check if token is expired
        if stored_token.expires_at < datetime.now(UTC):
            raise AuthenticationError("Token expired", "INVALID_TOKEN")

        # Get user
        user = self.repo.get_user_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("User not found", "USER_NOT_FOUND")

        # Revoke old token
        self.repo.revoke_refresh_token(token_hash)

        # Create new tokens
        new_access_token = create_access_token(user.id, user.email, user.is_verified)
        new_refresh_token, new_token_hash = create_refresh_token(user.id)

        # Store new refresh token
        expires_at = datetime.now(UTC) + timedelta(days=7)
        self.repo.create_refresh_token(
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=expires_at,
            ip_address=stored_token.ip_address,
            user_agent=stored_token.user_agent,
        )

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer",
            expires_in=900,
        )

    def logout(self, refresh_token: str) -> bool:
        """Logout user by revoking refresh token."""
        token_hash = get_token_hash(refresh_token)
        self.repo.revoke_refresh_token(token_hash)
        return True

    def logout_all(self, user_id: UUID) -> int:
        """Logout user from all sessions."""
        return self.repo.revoke_all_user_tokens(user_id)

    def initiate_password_reset(self, email: str, ip_address: str | None = None) -> str | None:
        """Initiate password reset flow."""
        rate_key = ip_address or email
        self._check_rate_limit(rate_key, "forgot_password")

        user = self.repo.get_user_by_email(email)
        if user is None:
            return None  # Don't reveal if user exists

        return create_password_reset_token(user.id, user.email)

    def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: str | None = None,
    ) -> bool:
        """Reset user password."""
        rate_key = ip_address or "reset"
        self._check_rate_limit(rate_key, "reset_password")

        # Decode and validate token
        payload = decode_token(token)
        if payload is None:
            raise AuthenticationError("Invalid or expired token", "INVALID_TOKEN")

        if payload.get("type") != "password_reset":
            raise AuthenticationError("Invalid token type", "INVALID_TOKEN")

        user_id = UUID(payload["sub"])

        # Update password
        password_hash = hash_password(new_password)
        user = self.repo.update_user(user_id, password_hash=password_hash)
        if user is None:
            raise AuthenticationError("User not found", "USER_NOT_FOUND")

        # Revoke all refresh tokens for user
        self.repo.revoke_all_user_tokens(user_id)

        return True

    def get_user_by_id(self, user_id: UUID) -> UserResponse | None:
        """Get user by ID."""
        user = self.repo.get_user_by_id(user_id)
        if user is None:
            return None

        return UserResponse(
            id=user.id,
            email=user.email,
            is_verified=user.is_verified,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login,
        )

    def get_current_user(self, access_token: str) -> UserResponse:
        """Get current user from access token."""
        payload = decode_token(access_token)
        if payload is None:
            raise AuthenticationError("Invalid or expired token", "INVALID_TOKEN")

        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type", "INVALID_TOKEN")

        user_id = UUID(payload["sub"])
        user = self.repo.get_user_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found", "USER_NOT_FOUND")

        if not user.is_active:
            raise AuthenticationError("Account disabled", "ACCOUNT_DISABLED")

        return UserResponse(
            id=user.id,
            email=user.email,
            is_verified=user.is_verified,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login,
        )

    def list_sessions(self, user_id: UUID) -> list[dict[str, Any]]:
        """List active sessions for user."""
        query = """
            SELECT token_hash, created_at, expires_at, ip_address, user_agent
            FROM refresh_tokens
            WHERE user_id = $1 AND revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP
            ORDER BY created_at DESC
        """
        results = self.repo.conn.execute(query, [str(user_id)]).fetchall()

        sessions = []
        for row in results:
            sessions.append(
                {
                    "token_hash": row[0][:8] + "...",  # Only show first 8 chars
                    "created_at": row[1],
                    "expires_at": row[2],
                    "ip_address": row[3],
                    "user_agent": row[4],
                }
            )

        return sessions

    def close(self) -> None:
        """Close the repository connection."""
        self.repo.close()
