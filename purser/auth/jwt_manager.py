"""JWT token manager for session management.

This module provides JWT token issuance, validation, and management
for the authentication system.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import jwt

from purser.auth.config import OAuthConfig  # noqa: TC001


class TokenType(Enum):
    """JWT token types."""

    ACCESS = "access"
    REFRESH = "refresh"


class JWTError(Exception):
    """Exception raised for JWT-related errors."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class TokenExpiredError(JWTError):
    """Exception raised when a token has expired."""

    pass


class TokenInvalidError(JWTError):
    """Exception raised when a token is invalid."""

    pass


class JWTManager:
    """Manager for JWT token operations.

    Handles token issuance, validation, and decoding for access
    and refresh tokens used in session management.
    """

    def __init__(self, config: OAuthConfig) -> None:
        """Initialize the JWT manager.

        Args:
            config: OAuth configuration containing JWT settings
        """
        self.config = config
        self.secret_key = config.jwt_secret
        self.algorithm = config.jwt_algorithm
        self.access_token_expire_minutes = config.access_token_expire_minutes
        self.refresh_token_expire_days = config.refresh_token_expire_days

    def create_access_token(
        self,
        user_id: str,
        email: str,
        is_verified: bool = True,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a new access token.

        Args:
            user_id: Unique user identifier
            email: User email address
            is_verified: Whether the user's email is verified
            extra_claims: Additional claims to include in the token

        Returns:
            Encoded JWT access token
        """
        expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        return self._create_token(
            user_id=user_id,
            email=email,
            is_verified=is_verified,
            token_type=TokenType.ACCESS,
            expires_delta=expires_delta,
            extra_claims=extra_claims,
        )

    def create_refresh_token(
        self,
        user_id: str,
        email: str,
        is_verified: bool = True,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a new refresh token.

        Args:
            user_id: Unique user identifier
            email: User email address
            is_verified: Whether the user's email is verified
            extra_claims: Additional claims to include in the token

        Returns:
            Encoded JWT refresh token
        """
        expires_delta = timedelta(days=self.refresh_token_expire_days)
        return self._create_token(
            user_id=user_id,
            email=email,
            is_verified=is_verified,
            token_type=TokenType.REFRESH,
            expires_delta=expires_delta,
            extra_claims=extra_claims,
        )

    def create_token_pair(
        self,
        user_id: str,
        email: str,
        is_verified: bool = True,
        extra_claims: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create both access and refresh tokens.

        Args:
            user_id: Unique user identifier
            email: User email address
            is_verified: Whether the user's email is verified
            extra_claims: Additional claims to include in the tokens

        Returns:
            Dictionary containing access_token, refresh_token, token_type, and expires_in
        """
        access_token = self.create_access_token(
            user_id=user_id,
            email=email,
            is_verified=is_verified,
            extra_claims=extra_claims,
        )
        refresh_token = self.create_refresh_token(
            user_id=user_id,
            email=email,
            is_verified=is_verified,
            extra_claims=extra_claims,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.access_token_expire_minutes * 60,
        }

    def _create_token(
        self,
        user_id: str,
        email: str,
        is_verified: bool,
        token_type: TokenType,
        expires_delta: timedelta,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a JWT token with the specified claims.

        Args:
            user_id: Unique user identifier
            email: User email address
            is_verified: Whether the user's email is verified
            token_type: Type of token (access or refresh)
            expires_delta: Token lifetime
            extra_claims: Additional claims to include

        Returns:
            Encoded JWT token
        """
        now = datetime.now(UTC)
        expires_at = now + expires_delta

        payload: dict[str, Any] = {
            "user_id": user_id,
            "email": email,
            "is_verified": is_verified,
            "type": token_type.value,
            "exp": expires_at,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }

        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str, token_type: TokenType | None = None) -> dict[str, Any]:
        """Decode and validate a JWT token.

        Args:
            token: The JWT token to decode
            token_type: Expected token type (optional validation)

        Returns:
            Decoded token payload

        Raises:
            TokenExpiredError: If the token has expired
            TokenInvalidError: If the token is invalid or has wrong type
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError("Token has expired", "TOKEN_EXPIRED") from e
        except jwt.InvalidTokenError as e:
            raise TokenInvalidError("Invalid token", "TOKEN_INVALID") from e

        # Validate token type if specified
        if token_type is not None and payload.get("type") != token_type.value:
            raise TokenInvalidError(f"Expected {token_type.value} token", "WRONG_TOKEN_TYPE")

        return payload

    def validate_access_token(self, token: str) -> dict[str, Any]:
        """Validate an access token.

        Args:
            token: The access token to validate

        Returns:
            Decoded token payload

        Raises:
            TokenExpiredError: If the token has expired
            TokenInvalidError: If the token is invalid or not an access token
        """
        return self.decode_token(token, token_type=TokenType.ACCESS)

    def validate_refresh_token(self, token: str) -> dict[str, Any]:
        """Validate a refresh token.

        Args:
            token: The refresh token to validate

        Returns:
            Decoded token payload

        Raises:
            TokenExpiredError: If the token has expired
            TokenInvalidError: If the token is invalid or not a refresh token
        """
        return self.decode_token(token, token_type=TokenType.REFRESH)

    def get_token_expiry(self, token: str) -> datetime:
        """Get the expiration time of a token.

        Args:
            token: The JWT token

        Returns:
            Token expiration datetime

        Raises:
            TokenInvalidError: If the token cannot be decoded
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )
            exp = payload.get("exp")
            if exp is None:
                raise TokenInvalidError("Token has no expiration", "NO_EXPIRATION")
            return datetime.fromtimestamp(exp, tz=UTC)
        except jwt.InvalidTokenError as e:
            raise TokenInvalidError("Cannot decode token", "DECODE_ERROR") from e

    def is_token_expired(self, token: str) -> bool:
        """Check if a token is expired.

        Args:
            token: The JWT token to check

        Returns:
            True if the token is expired, False otherwise
        """
        try:
            self.decode_token(token)
            return False
        except TokenExpiredError:
            return True
        except TokenInvalidError:
            return True

    def get_token_id(self, token: str) -> str | None:
        """Get the unique identifier (jti) from a token.

        Args:
            token: The JWT token

        Returns:
            Token JTI or None if not present
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )
            return payload.get("jti")
        except jwt.InvalidTokenError:
            return None

    def rotate_refresh_token(
        self, old_refresh_token: str, extra_claims: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Rotate a refresh token (issue new tokens, invalidate old).

        Args:
            old_refresh_token: The current refresh token
            extra_claims: Additional claims for the new tokens

        Returns:
            New token pair (access_token, refresh_token, token_type, expires_in)

        Raises:
            TokenExpiredError: If the old token has expired
            TokenInvalidError: If the old token is invalid
        """
        # Validate the old refresh token
        payload = self.validate_refresh_token(old_refresh_token)

        # Extract user info
        user_id = payload.get("user_id")
        email = payload.get("email")
        is_verified = payload.get("is_verified", True)

        if not user_id or not email:
            raise TokenInvalidError("Token missing required claims", "MISSING_CLAIMS")

        # Create new token pair
        return self.create_token_pair(
            user_id=user_id,
            email=email,
            is_verified=is_verified,
            extra_claims=extra_claims,
        )
