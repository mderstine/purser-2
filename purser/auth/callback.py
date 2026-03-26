"""OAuth callback handler for processing provider responses.

This module handles OAuth callbacks from providers including:
- State validation (CSRF protection)
- Error handling
- Token exchange
- User creation/linking
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from purser.auth.github import GitHubOAuth, GitHubOAuthError
from purser.auth.google import GoogleOAuth, GoogleOAuthError
from purser.auth.models import OAuthAccount, OAuthToken, User, UserInfo

if TYPE_CHECKING:
    from purser.auth.config import OAuthConfig


class OAuthCallbackError(Exception):
    """Exception raised for OAuth callback errors."""

    def __init__(
        self, message: str, error_code: str | None = None, provider: str | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "oauth_error"
        self.provider = provider


class OAuthCallbackHandler:
    """Handler for OAuth provider callbacks."""

    def __init__(self, config: OAuthConfig) -> None:
        """Initialize with OAuth configuration.

        Args:
            config: OAuth configuration containing provider settings
        """
        self.config = config
        self._state_store: dict[str, dict[str, Any]] = {}  # In-memory state store

    async def handle_callback(
        self,
        provider: str,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
        expected_state: str | None = None,
    ) -> dict[str, Any]:
        """Handle OAuth callback from provider.

        Args:
            provider: OAuth provider name ("google" or "github")
            code: Authorization code from provider
            state: State parameter from provider
            error: Error code if provider returned error
            error_description: Error description from provider
            expected_state: Expected state value for validation

        Returns:
            Dictionary containing tokens and user info

        Raises:
            OAuthCallbackError: If callback processing fails
        """
        # Check for provider error
        if error:
            raise OAuthCallbackError(
                message=error_description or f"OAuth error: {error}",
                error_code=error,
                provider=provider,
            )

        # Validate required parameters
        if not code:
            raise OAuthCallbackError(
                message="Authorization code is required",
                error_code="missing_code",
                provider=provider,
            )

        if not state:
            raise OAuthCallbackError(
                message="State parameter is required",
                error_code="missing_state",
                provider=provider,
            )

        # Validate state (CSRF protection)
        if not self._validate_state(state, expected_state):
            raise OAuthCallbackError(
                message="Invalid state parameter",
                error_code="invalid_state",
                provider=provider,
            )

        # Exchange code for tokens based on provider
        if provider == "google":
            return await self._handle_google_callback(code, state)
        elif provider == "github":
            return await self._handle_github_callback(code, state)
        else:
            raise OAuthCallbackError(
                message=f"Unsupported OAuth provider: {provider}",
                error_code="unsupported_provider",
                provider=provider,
            )

    async def _handle_google_callback(self, code: str, state: str) -> dict[str, Any]:
        """Handle Google OAuth callback.

        Args:
            code: Authorization code from Google
            state: State parameter from callback

        Returns:
            Dictionary with tokens and user info
        """
        try:
            google = GoogleOAuth(self.config)

            # Exchange code for tokens
            token_data = await google.exchange_code(code)

            # Get user info
            user_info = await google.get_user_info(token_data.access_token)

            # Build response
            return {
                "provider": "google",
                "user_info": user_info.model_dump(exclude={"raw_data"}),
                "token": token_data.model_dump(),
                "success": True,
            }

        except GoogleOAuthError as e:
            raise OAuthCallbackError(
                message=str(e),
                error_code=e.error_code or "google_error",
                provider="google",
            ) from e

    async def _handle_github_callback(self, code: str, state: str) -> dict[str, Any]:
        """Handle GitHub OAuth callback.

        Args:
            code: Authorization code from GitHub
            state: State parameter from callback

        Returns:
            Dictionary with tokens and user info
        """
        try:
            github = GitHubOAuth(self.config)

            # Exchange code for tokens
            token_data = await github.exchange_code(code)

            # Get user info
            user_info = await github.get_user_info(token_data.access_token)

            # Build response
            return {
                "provider": "github",
                "user_info": user_info.model_dump(exclude={"raw_data"}),
                "token": token_data.model_dump(),
                "success": True,
            }

        except GitHubOAuthError as e:
            raise OAuthCallbackError(
                message=str(e),
                error_code=e.error_code or "github_error",
                provider="github",
            ) from e

    def _validate_state(self, state: str, expected_state: str | None = None) -> bool:
        """Validate OAuth state parameter.

        Args:
            state: State from callback
            expected_state: Expected state value

        Returns:
            True if state is valid
        """
        if expected_state:
            # Handle state with embedded redirect
            actual_state = state.split(":", 1)[0] if ":" in state else state
            return actual_state == expected_state

        # If no expected state provided, check store
        return state in self._state_store

    def store_state(self, state: str, data: dict[str, Any]) -> None:
        """Store state token with associated data.

        Args:
            state: State token
            data: Associated data (redirect_after, provider, etc.)
        """
        self._state_store[state] = data

    def clear_state(self, state: str) -> None:
        """Remove state from store.

        Args:
            state: State token to remove
        """
        self._state_store.pop(state, None)

    def get_stored_state(self, state: str) -> dict[str, Any] | None:
        """Get stored state data.

        Args:
            state: State token

        Returns:
            Stored data or None
        """
        return self._state_store.get(state)


class OAuthUserManager:
    """Manager for OAuth user accounts."""

    def __init__(self) -> None:
        """Initialize user manager."""
        self._users: dict[str, User] = {}  # email -> User
        self._oauth_accounts: dict[
            str, OAuthAccount
        ] = {}  # (provider, provider_user_id) -> OAuthAccount

    def find_or_create_user(
        self,
        user_info: UserInfo,
        oauth_token: OAuthToken,
    ) -> tuple[User, bool]:
        """Find existing user or create new one from OAuth data.

        Args:
            user_info: User info from OAuth provider
            oauth_token: OAuth token data

        Returns:
            Tuple of (User, is_new)
        """
        if not user_info.email:
            raise OAuthCallbackError(
                message="OAuth provider did not return email",
                error_code="missing_email",
                provider=user_info.provider,
            )

        # Check for existing user by email
        existing_user = self._users.get(user_info.email)

        if existing_user:
            # Link OAuth account to existing user
            self._link_oauth_account(existing_user, user_info, oauth_token)
            return existing_user, False

        # Create new user
        new_user = User(
            email=user_info.email,
            is_verified=user_info.email_verified,
            password_hash=None,  # OAuth-only user
        )
        self._users[user_info.email] = new_user

        # Create OAuth account
        self._link_oauth_account(new_user, user_info, oauth_token)

        return new_user, True

    def _link_oauth_account(
        self,
        user: User,
        user_info: UserInfo,
        oauth_token: OAuthToken,
    ) -> OAuthAccount:
        """Link OAuth account to user.

        Args:
            user: User to link to
            user_info: OAuth user info
            oauth_token: OAuth token

        Returns:
            Linked OAuth account
        """
        from datetime import datetime, timedelta

        # Calculate expiration
        expires_at = None
        if oauth_token.expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=oauth_token.expires_in)

        account = OAuthAccount(
            user_id=user.id,
            provider=user_info.provider,
            provider_user_id=user_info.id,
            email=user_info.email,
            access_token_encrypted=oauth_token.access_token,  # Should be encrypted in production
            refresh_token_encrypted=oauth_token.refresh_token,
            expires_at=expires_at,
        )

        key = f"{user_info.provider}:{user_info.id}"
        self._oauth_accounts[key] = account

        return account

    def get_user_by_oauth(self, provider: str, provider_user_id: str) -> User | None:
        """Get user by OAuth provider and user ID.

        Args:
            provider: OAuth provider name
            provider_user_id: Provider's user ID

        Returns:
            User if found, None otherwise
        """
        key = f"{provider}:{provider_user_id}"
        account = self._oauth_accounts.get(key)
        if account:
            return self._users.get(account.email)
        return None

    def unlink_oauth_account(self, user: User, provider: str) -> bool:
        """Unlink OAuth account from user.

        Args:
            user: User to unlink from
            provider: OAuth provider name

        Returns:
            True if account was unlinked
        """
        # Find account by user_id and provider
        for key, account in list(self._oauth_accounts.items()):
            if str(account.user_id) == str(user.id) and account.provider == provider:
                del self._oauth_accounts[key]
                return True
        return False
