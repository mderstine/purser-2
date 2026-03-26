"""Main OAuth handler that coordinates all OAuth2 providers.

This module provides a unified interface for:
- Initializing OAuth flows
- Handling callbacks
- Managing user accounts
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from purser.auth.callback import OAuthCallbackError, OAuthCallbackHandler, OAuthUserManager
from purser.auth.github import GitHubOAuth
from purser.auth.google import GoogleOAuth
from purser.auth.models import AuthTokens, User, UserInfo

if TYPE_CHECKING:
    from purser.auth.config import OAuthConfig


class OAuthHandler:
    """Main OAuth handler coordinating all providers."""

    def __init__(self, config: OAuthConfig) -> None:
        """Initialize OAuth handler with configuration.

        Args:
            config: OAuth configuration containing provider settings
        """
        self.config = config
        self.callback_handler = OAuthCallbackHandler(config)
        self.user_manager = OAuthUserManager()

    def get_authorization_url(
        self,
        provider: str,
        state: str | None = None,
        redirect_after: str | None = None,
    ) -> tuple[str, str]:
        """Get OAuth authorization URL for provider.

        Args:
            provider: OAuth provider name ("google" or "github")
            state: Optional state parameter
            redirect_after: Optional redirect URL after authorization

        Returns:
            Tuple of (authorization_url, state)

        Raises:
            OAuthCallbackError: If provider is not configured
        """
        if provider == "google":
            google = GoogleOAuth(self.config)
            url, state = google.get_authorization_url(state, redirect_after)
        elif provider == "github":
            github = GitHubOAuth(self.config)
            url, state = github.get_authorization_url(state, redirect_after)
        else:
            raise OAuthCallbackError(
                message=f"Unsupported OAuth provider: {provider}",
                error_code="unsupported_provider",
                provider=provider,
            )

        # Store state for validation
        self.callback_handler.store_state(
            state,
            {
                "provider": provider,
                "redirect_after": redirect_after,
            },
        )

        return url, state

    async def handle_callback(
        self,
        provider: str,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
    ) -> dict:
        """Handle OAuth callback from provider.

        Args:
            provider: OAuth provider name
            code: Authorization code
            state: State parameter
            error: Error code from provider
            error_description: Error description from provider

        Returns:
            Dictionary with authentication result
        """
        # Get expected state from store
        expected_state = state
        if state:
            stored = self.callback_handler.get_stored_state(state)
            if stored:
                expected_state = state

        result = await self.callback_handler.handle_callback(
            provider=provider,
            code=code,
            state=state,
            error=error,
            error_description=error_description,
            expected_state=expected_state,
        )

        # Clear used state
        if state:
            self.callback_handler.clear_state(state)

        return result

    async def authenticate_user(
        self,
        provider: str,
        code: str,
        state: str,
    ) -> dict:
        """Complete OAuth flow and authenticate user.

        This method:
        1. Handles the OAuth callback
        2. Gets user info from provider
        3. Creates or links user account
        4. Returns auth tokens

        Args:
            provider: OAuth provider name
            code: Authorization code
            state: State parameter

        Returns:
            Dictionary with user, tokens, and auth result
        """
        from purser.auth.models import OAuthToken

        # Handle callback
        callback_result = await self.handle_callback(provider, code, state)

        if not callback_result.get("success"):
            return {
                "success": False,
                "error": callback_result.get("error", "OAuth failed"),
            }

        # Get user info and token from callback
        user_info_data = callback_result.get("user_info", {})
        token_data = callback_result.get("token", {})

        user_info = UserInfo(**user_info_data)
        oauth_token = OAuthToken(**token_data)

        # Find or create user
        user, is_new = self.user_manager.find_or_create_user(user_info, oauth_token)

        # Generate JWT tokens (placeholder - would use actual JWT implementation)
        auth_tokens = self._generate_tokens(user)

        return {
            "success": True,
            "user": user.to_dict(),
            "is_new_user": is_new,
            "provider": provider,
            "tokens": auth_tokens.model_dump()
            if hasattr(auth_tokens, "model_dump")
            else auth_tokens,
        }

    def _generate_tokens(self, user: User) -> AuthTokens:
        """Generate JWT tokens for authenticated user.

        Args:
            user: Authenticated user

        Returns:
            AuthTokens with access and refresh tokens
        """
        # This is a placeholder - in production, use proper JWT library
        # like python-jose or PyJWT with proper signing
        import secrets

        access_token = f"access_{secrets.token_urlsafe(32)}_{user.id}"
        refresh_token = f"refresh_{secrets.token_urlsafe(32)}_{user.id}"

        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self.config.access_token_expire_minutes * 60,
        )

    def unlink_provider(self, user: User, provider: str) -> bool:
        """Unlink OAuth provider from user account.

        Args:
            user: User to unlink provider from
            provider: OAuth provider name

        Returns:
            True if provider was unlinked
        """
        return self.user_manager.unlink_oauth_account(user, provider)

    def get_user_providers(self, user: User) -> list[str]:
        """Get list of linked OAuth providers for user.

        Args:
            user: User to get providers for

        Returns:
            List of provider names
        """
        providers = []
        # This would query the database for linked accounts
        # For now, return empty list as a placeholder
        return providers
