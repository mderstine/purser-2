"""GitHub OAuth2 integration.

This module provides GitHub OAuth2 authentication flow including:
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
    from purser.auth.config import OAuthConfig, OAuthProviderConfig


class GitHubOAuthError(Exception):
    """Exception raised for GitHub OAuth errors."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class GitHubOAuth:
    """GitHub OAuth2 handler."""

    def __init__(self, config: OAuthConfig) -> None:
        """Initialize with OAuth configuration.

        Args:
            config: OAuth configuration containing GitHub provider settings
        """
        self.config = config
        self.provider_config: OAuthProviderConfig | None = config.get_provider("github")
        if not self.provider_config:
            raise GitHubOAuthError("GitHub OAuth provider not configured")

    def get_authorization_url(
        self,
        state: str | None = None,
        redirect_after: str | None = None,
    ) -> tuple[str, str]:
        """Generate GitHub OAuth authorization URL.

        Args:
            state: Optional state parameter (generated if not provided)
            redirect_after: Optional URL to redirect to after authorization

        Returns:
            Tuple of (authorization_url, state)
        """
        if not self.provider_config:
            raise GitHubOAuthError("GitHub OAuth provider not configured")

        # Generate state if not provided (for CSRF protection)
        if state is None:
            state = secrets.token_urlsafe(32)

        # Build authorization URL with required parameters
        params: dict[str, str] = {
            "client_id": self.provider_config.client_id,
            "redirect_uri": self.provider_config.redirect_uri,
            "scope": " ".join(self.provider_config.scopes),
            "state": state,
        }

        # Build query string
        query = "&".join(f"{k}={httpx.URL.encode(v)}" for k, v in params.items())
        auth_url = f"{self.provider_config.authorization_url}?{query}"

        return auth_url, state

    async def exchange_code(self, code: str) -> OAuthToken:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from GitHub callback

        Returns:
            OAuthToken containing access_token

        Raises:
            GitHubOAuthError: If token exchange fails
        """
        if not self.provider_config:
            raise GitHubOAuthError("GitHub OAuth provider not configured")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.provider_config.token_url,
                headers={
                    "Accept": "application/json",
                },
                data={
                    "client_id": self.provider_config.client_id,
                    "client_secret": self.provider_config.client_secret,
                    "code": code,
                    "redirect_uri": self.provider_config.redirect_uri,
                },
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get(
                    "error_description", error_data.get("error", "Unknown error")
                )
                raise GitHubOAuthError(
                    f"Token exchange failed: {error_msg}",
                    error_code=error_data.get("error"),
                )

            data = response.json()

            # GitHub returns 'token_type' as lower case
            return OAuthToken(
                access_token=data["access_token"],
                token_type=data.get("token_type", "Bearer").capitalize(),
                scope=data.get("scope"),
            )

    async def get_user_info(self, access_token: str) -> UserInfo:
        """Retrieve user information from GitHub.

        Args:
            access_token: Valid GitHub access token

        Returns:
            UserInfo containing user's GitHub profile data

        Raises:
            GitHubOAuthError: If user info request fails
        """
        if not self.provider_config:
            raise GitHubOAuthError("GitHub OAuth provider not configured")

        async with httpx.AsyncClient() as client:
            # Get user profile
            response = await client.get(
                self.provider_config.userinfo_url,
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                raise GitHubOAuthError(
                    f"Failed to retrieve user info: {error_data}",
                    error_code="userinfo_failed",
                )

            user_data: dict[str, Any] = response.json()

            # GitHub may not return email in user endpoint, need to fetch separately
            email = user_data.get("email")
            if not email:
                email = await self._get_user_email(access_token)

            return UserInfo(
                id=str(user_data.get("id", "")),
                email=email,
                email_verified=bool(email),  # GitHub verified emails only
                name=user_data.get("name") or user_data.get("login"),
                picture=user_data.get("avatar_url"),
                provider="github",
                raw_data=user_data,
            )

    async def _get_user_email(self, access_token: str) -> str | None:
        """Fetch user's primary email from GitHub.

        Args:
            access_token: Valid GitHub access token

        Returns:
            Primary email address or None
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )

            if response.status_code != 200:
                return None

            emails: list[dict[str, Any]] = response.json()

            # Return primary verified email
            for email_data in emails:
                if email_data.get("primary") and email_data.get("verified"):
                    return email_data.get("email")

            # Fall back to first verified email
            for email_data in emails:
                if email_data.get("verified"):
                    return email_data.get("email")

            return None

    def validate_state(self, state: str, expected_state: str | None = None) -> bool:
        """Validate OAuth state parameter.

        Args:
            state: State parameter from callback
            expected_state: Expected state value (if pre-generated)

        Returns:
            True if state is valid
        """
        if expected_state:
            return state == expected_state
        # GitHub doesn't embed data in state, just validate format
        return len(state) >= 16  # Basic length check
