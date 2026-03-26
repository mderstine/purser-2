"""Security utilities for authentication."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
import jwt

# Configuration - In production these should come from environment variables
JWT_SECRET_KEY = secrets.token_urlsafe(32)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
VERIFICATION_TOKEN_EXPIRE_HOURS = 24
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 1


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    plain_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def create_access_token(user_id: UUID, email: str, is_verified: bool) -> str:
    """Create a JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "verified": is_verified,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: UUID) -> tuple[str, str]:
    """Create a JWT refresh token and return token with hash.

    Returns:
        Tuple of (token, token_hash) for storage.
    """
    expire = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    token_id = secrets.token_urlsafe(32)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": token_id,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    # Hash the token for storage
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def create_verification_token(user_id: UUID, email: str) -> str:
    """Create a JWT email verification token."""
    expire = datetime.now(UTC) + timedelta(hours=VERIFICATION_TOKEN_EXPIRE_HOURS)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "type": "verification",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_password_reset_token(user_id: UUID, email: str) -> str:
    """Create a JWT password reset token."""
    expire = datetime.now(UTC) + timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "type": "password_reset",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token.

    Returns:
        The decoded payload if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_token_hash(token: str) -> str:
    """Get SHA256 hash of a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_random_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)
