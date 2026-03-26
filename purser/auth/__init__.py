"""Authentication module for OAuth2 integration and session management.

This module provides OAuth2 authentication with Google and GitHub,
callback handling, user management, and JWT-based session management
including token issuance, refresh, and invalidation.

Also includes email/password authentication with registration, email verification,
login with rate limiting, and password reset flows.
"""

from __future__ import annotations

from purser.auth.callback import OAuthCallbackError, OAuthCallbackHandler, OAuthUserManager
from purser.auth.config import OAuthConfig, OAuthProviderConfig
from purser.auth.github import GitHubOAuth, GitHubOAuthError
from purser.auth.google import GoogleOAuth, GoogleOAuthError
from purser.auth.handler import OAuthHandler
from purser.auth.jwt_manager import (
    JWTError,
    JWTManager,
    TokenExpiredError,
    TokenInvalidError,
    TokenType,
)
from purser.auth.models import (
    AuthTokens,
    OAuthAccount,
    OAuthState,
    OAuthToken,
    RefreshToken,
    TokenResponse,
    User,
    UserCreate,
    UserInfo,
    UserLogin,
    UserResponse,
)
from purser.auth.repository import AuthRepository
from purser.auth.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    create_verification_token,
    decode_token,
    hash_password,
    verify_password,
)
from purser.auth.service import AuthenticationError, AuthService, RateLimitExceededError
from purser.auth.session_manager import (
    SessionError,
    SessionInfo,
    SessionManager,
    SessionRevokedError,
    TokenPair,
)

__all__ = [
    # Email/Password Auth
    "AuthService",
    "AuthenticationError",
    "RateLimitExceededError",
    "AuthRepository",
    "RefreshToken",
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    # Security
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "create_verification_token",
    "create_password_reset_token",
    "decode_token",
    # OAuth2
    "AuthTokens",
    "GitHubOAuth",
    "GitHubOAuthError",
    "GoogleOAuth",
    "GoogleOAuthError",
    "JWTError",
    "JWTManager",
    "OAuthAccount",
    "OAuthCallbackError",
    "OAuthCallbackHandler",
    "OAuthConfig",
    "OAuthHandler",
    "OAuthProviderConfig",
    "OAuthState",
    "OAuthToken",
    "OAuthUserManager",
    "SessionError",
    "SessionInfo",
    "SessionManager",
    "SessionRevokedError",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenPair",
    "TokenType",
    "User",
    "UserInfo",
]
