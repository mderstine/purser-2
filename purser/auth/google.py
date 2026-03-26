"""Google OAuth2 integration.

This module provides Google OAuth2 authentication flow including:
- Authorization URL generation
- Token exchange
- User info retrieval
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any

import httpx

from purser.auth.models import OAuthToken, UserInfo

if TYPE_CHECKING:
    from purser.auth.config import OAuthConfig


class GoogleOAuthError(Exception):
    """Exception raised for Google OAuth errors."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class GoogleOAuth:
    """Google OAuth2 handler."""

    def __init__(self, config: OAuthConfig) -> None:
        """Initialize with OAuth configuration.

        Args:
            config: OAuth configuration containing Google provider settings
        """
        self.config = config
        self.provider_config = config.get_provider("google")
        if not self.provider_config:
            raise GoogleOAuthError("Google OAuth provider not configured")

    def get_authorization_url(
        self,
        state: str | None = None,
        redirect_after: str | None = None,
    ) -> tuple[str, str]:
        """Generate Google OAuth authorization URL.

        Args:
            state: Optional state parameter (generated if not provided)
            redirect_after: Optional URL to redirect to after authorization

        Returns:
            Tuple of (authorization_url, state)
        """
        if not self.provider_config:
            raise GoogleOAuthError("Google OAuth provider not configured")

        # Generate state if not provided (for CSRF protection)
        if state is None:
            state = secrets.token_urlsafe(32)

        # Build authorization URL with required parameters
        params: dict[str, str] = {
            "client_id": self.provider_config.client_id,
            "redirect_uri": self.provider_config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.provider_config.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }

        # Add custom state data for redirect_after if provided
        if redirect_after:
            # Store redirect_after in state (could be encoded/encrypted in production)
            params["state"] = f"{state}:{redirect_after}"

        # Build query string
        query = "&".join(f"{k}={httpx.URL.encode(v)}" for k, v in params.items())
        auth_url = f"{self.provider_config.authorization_url}?{query}"

        return auth_url, state

    async def exchange_code(self, code: str) -> OAuthToken:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from Google callback

        Returns:
            OAuthToken containing access_token and optional refresh_token

        Raises:
            GoogleOAuthError: If token exchange fails
        """
        if not self.provider_config:
            raise GoogleOAuthError("Google OAuth provider not configured")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.provider_config.token_url,
                data={
                    "client_id": self.provider_config.client_id,
                    "client_secret": self.provider_config.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.provider_config.redirect_uri,
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get(
                    "error_description", error_data.get("error", "Unknown error")
                )
                raise GoogleOAuthError(
                    f"Token exchange failed: {error_msg}",
                    error_code=error_data.get("error"),
                )

            data = response.json()
            return OAuthToken(
                access_token=data["access_token"],
                token_type=data.get("token_type", "Bearer"),
                expires_in=data.get("expires_in"),
                refresh_token=data.get("refresh_token"),
                scope=data.get("scope"),
            )

    async def get_user_info(self, access_token: str) -> UserInfo:
        """Retrieve user information from Google.

        Args:
            access_token: Valid Google access token

        Returns:
            UserInfo containing user's Google profile data

        Raises:
            GoogleOAuthError: If user info request fails
        """
        if not self.provider_config:
            raise GoogleOAuthError("Google OAuth provider not configured")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.provider_config.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                raise GoogleOAuthError(
                    f"Failed to retrieve user info: {error_data}",
                    error_code="userinfo_failed",
                )

            data: dict[str, Any] = response.json()

            return UserInfo(
                id=data.get("id", ""),
                email=data.get("email"),
                email_verified=data.get("verified_email", False),
                name=data.get("name"),
                picture=data.get("picture"),
                provider="google",
                raw_data=data,
            )

    async def refresh_access_token(self, refresh_token: str) -> OAuthToken:
        """Refresh an expired access token.

        Args:
            refresh_token: Refresh token from initial OAuth flow

        Returns:
            New OAuthToken with updated access_token

        Raises:
            GoogleOAuthError: If token refresh fails
        """
        if not self.provider_config:
            raise GoogleOAuthError("Google OAuth provider not configured")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.provider_config.token_url,
                data={
                    "client_id": self.provider_config.client_id,
                    "client_secret": self.provider_config.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get(
                    "error_description", error_data.get("error", "Unknown error")
                )
                raise GoogleOAuthError(
                    f"Token refresh failed: {error_msg}",
                    error_code=error_data.get("error"),
                )

            data = response.json()
            return OAuthToken(
                access_token=data["access_token"],
                token_type=data.get("token_type", "Bearer"),
                expires_in=data.get("expires_in"),
                refresh_token=refresh_token,  # Keep original refresh token
                scope=data.get("scope"),
            )

    def validate_state(
        self, state: str, expected_state: str | None = None
    ) -> tuple[bool, str | None]:
        """Validate OAuth state parameter.

        Args:
            state: State parameter from callback
            expected_state: Expected state value (if pre-generated)

        Returns:
            Tuple of (is_valid, redirect_after)
        """
        if expected_state and state != expected_state:
            return False, None

        # Check for embedded redirect_after in state
        redirect_after: str | None = None
        if ":" in state:
            parts = state.split(":", 1)
            if len(parts) == 2:
                state = parts[0]
                redirect_after = parts[1]

        return True, redirect_after
