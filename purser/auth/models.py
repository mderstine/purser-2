"""Data models for OAuth2 authentication."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """User registration request."""

    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password meets requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """User login request."""

    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response without sensitive data."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    email: EmailStr
    is_verified: bool
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None


class TokenResponse(BaseModel):
    """Token response for login/refresh."""

    model_config = ConfigDict(extra="ignore")

    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = 3600  # 1 hour


class RefreshToken(BaseModel):
    """Refresh token for session management."""

    model_config = ConfigDict(extra="ignore")

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    token_hash: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    revoked_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None


class User(BaseModel):
    """User entity for authentication."""

    model_config = ConfigDict(extra="ignore")

    id: UUID = Field(default_factory=uuid4)
    email: str
    password_hash: str | None = None  # Nullable for OAuth-only users
    is_verified: bool = False
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excluding sensitive fields)."""
        return {
            "id": str(self.id),
            "email": self.email,
            "is_verified": self.is_verified,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class OAuthAccount(BaseModel):
    """OAuth account linked to a user."""

    model_config = ConfigDict(extra="ignore")

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    provider: str  # "google" or "github"
    provider_user_id: str
    email: str | None = None  # Cached email from provider
    access_token_encrypted: str | None = None
    refresh_token_encrypted: str | None = None
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excluding sensitive tokens)."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "provider": self.provider,
            "provider_user_id": self.provider_user_id,
            "email": self.email,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OAuthToken(BaseModel):
    """OAuth token response from provider."""

    model_config = ConfigDict(extra="ignore")

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 60 second buffer)."""
        if self.expires_in is None:
            return False
        return False  # Would need created_at to check properly


class UserInfo(BaseModel):
    """User information from OAuth provider."""

    model_config = ConfigDict(extra="ignore")

    id: str  # Provider-specific user ID
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None
    provider: str
    raw_data: dict[str, Any] = Field(default_factory=dict)


class AuthTokens(BaseModel):
    """JWT tokens issued after successful authentication."""

    model_config = ConfigDict(extra="ignore")

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class OAuthState(BaseModel):
    """OAuth state token for CSRF protection."""

    model_config = ConfigDict(extra="ignore")

    state: str
    provider: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    redirect_after: str | None = None

    def is_valid(self, ttl_seconds: int = 600) -> bool:
        """Check if state token is still valid."""
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed < ttl_seconds
