"""OAuth2 configuration for authentication providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class OAuthProviderConfig:
    """Configuration for a single OAuth2 provider."""

    name: Literal["google", "github"]
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    userinfo_url: str
    scopes: list[str]
    redirect_uri: str

    @classmethod
    def google(
        cls,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: list[str] | None = None,
    ) -> OAuthProviderConfig:
        """Create Google OAuth2 configuration."""
        return cls(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://www.googleapis.com/oauth2/v2/userinfo",
            scopes=scopes or ["openid", "email", "profile"],
            redirect_uri=redirect_uri,
        )

    @classmethod
    def github(
        cls,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: list[str] | None = None,
    ) -> OAuthProviderConfig:
        """Create GitHub OAuth2 configuration."""
        return cls(
            name="github",
            client_id=client_id,
            client_secret=client_secret,
            authorization_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            userinfo_url="https://api.github.com/user",
            scopes=scopes or ["user:email", "read:user"],
            redirect_uri=redirect_uri,
        )


@dataclass
class OAuthConfig:
    """Complete OAuth2 configuration."""

    providers: dict[str, OAuthProviderConfig]
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    state_ttl_seconds: int = 600  # 10 minutes for CSRF state tokens

    def get_provider(self, name: str) -> OAuthProviderConfig | None:
        """Get provider configuration by name."""
        return self.providers.get(name)

    def add_provider(self, config: OAuthProviderConfig) -> None:
        """Add a provider configuration."""
        self.providers[config.name] = config
