---
id: arch-user-authentication-system
title: User Authentication System Architecture
created: 2026-03-26
source: derived from spec-user-authentication-system
---

# User Authentication System Architecture

## Overview

This document describes the technical architecture for the Purser user authentication system, supporting email/password and OAuth2 authentication with JWT-based session management.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ /register   │  │ /login      │  │ /oauth/{provider}      │ │
│  │ /verify     │  │ /refresh    │  │ /oauth/callback/{prov} │ │
│  │ /resend     │  │ /logout     │  │                         │ │
│  │ /forgot     │  │             │  │                         │ │
│  │ /reset      │  │             │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Authentication Service                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Credential  │  │ JWT Manager │  │ OAuth2 Handler          │ │
│  │ Validator   │  │             │  │ (Google, GitHub)        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐                               │
│  │ Rate Limiter│  │ Email Sender│                               │ │
│  └─────────────┘  └─────────────┘                               │ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Data Layer                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Users Table │  │ Sessions    │  │ Tokens Table            │ │
│  │             │  │ Table       │  │ (refresh/blacklist)     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│  ┌─────────────┐                                                 │
│  │ OAuth Accounts│                                                │
│  │ (linked)    │                                                  │
│  └─────────────┘                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Data Models

### User Entity

```python
class User:
    id: UUID              # Primary key
    email: str            # Unique, indexed
    password_hash: str    # bcrypt hash (nullable for OAuth-only)
    is_verified: bool     # Email verification status
    is_active: bool       # Account status
    created_at: datetime
    updated_at: datetime
    last_login: datetime  # Nullable
```

### OAuth Account Entity

```python
class OAuthAccount:
    id: UUID
    user_id: UUID         # Foreign key → User.id
    provider: str         # "google", "github"
    provider_user_id: str # Provider's user ID
    email: str            # Cached email from provider
    access_token: str     # Encrypted
    refresh_token: str    # Encrypted (nullable)
    expires_at: datetime  # Token expiration
    created_at: datetime
    updated_at: datetime
```

### Session/Token Entity

```python
class RefreshToken:
    id: UUID
    user_id: UUID         # Foreign key → User.id
    token_hash: str       # SHA256 hash of token
    expires_at: datetime
    created_at: datetime
    revoked_at: datetime  # Nullable
    ip_address: str       # For audit
    user_agent: str       # For audit
```

## API Design

### Endpoints

#### Email/Password Authentication

| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| POST | `/auth/register` | Create new account | 5/min |
| POST | `/auth/verify` | Verify email with token | 10/min |
| POST | `/auth/resend-verification` | Resend verification email | 3/min |
| POST | `/auth/login` | Authenticate and get tokens | 10/min |
| POST | `/auth/forgot-password` | Initiate password reset | 3/min |
| POST | `/auth/reset-password` | Complete password reset | 10/min |

#### Session Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/refresh` | Get new access token | Refresh token |
| POST | `/auth/logout` | Revoke current session | Access token |
| POST | `/auth/logout-all` | Revoke all sessions | Access token |
| GET | `/auth/sessions` | List active sessions | Access token |

#### OAuth2

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/oauth/{provider}` | Initiate OAuth flow |
| GET | `/auth/oauth/callback/{provider}` | OAuth callback handler |
| POST | `/auth/oauth/unlink/{provider}` | Unlink OAuth account |

### Request/Response Examples

#### Registration
```json
// POST /auth/register
// Request
{
  "email": "user@example.com",
  "password": "securePassword123!"
}

// Response 201
{
  "user_id": "uuid",
  "email": "user@example.com",
  "message": "Verification email sent"
}
```

#### Login
```json
// POST /auth/login
// Request
{
  "email": "user@example.com",
  "password": "securePassword123!"
}

// Response 200
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

## Security Architecture

### Password Security

- **Hashing**: bcrypt with cost factor 12
- **Requirements**: Minimum 8 chars, 1 uppercase, 1 lowercase, 1 number
- **Storage**: Never store plaintext passwords

### JWT Token Strategy

```
Access Token:
- Lifetime: 15 minutes
- Contains: user_id, email, is_verified
- Secret: Server-side symmetric key (HS256)

Refresh Token:
- Lifetime: 7 days
- Storage: Database (for revocation)
- Rotation: New token issued on refresh, old token invalidated
```

### Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/auth/login` | 10 | 15 min |
| `/auth/register` | 5 | 15 min |
| `/auth/forgot-password` | 3 | 1 hour |
| `/auth/*` | 100 | 15 min (default) |

### OAuth2 Security

- **State Parameter**: Required for CSRF protection
- **PKCE**: Optional (recommend for mobile)
- **Token Storage**: Encrypted at rest
- **Scope**: Minimal (email, profile only)

## Email Flows

### Verification Email
1. User registers → verification token generated (JWT, 24h expiry)
2. Email sent with verification link
3. User clicks link → token validated → account verified
4. On success, redirect to login page

### Password Reset
1. User requests reset → reset token generated (JWT, 1h expiry)
2. Email sent with secure reset link
3. User submits new password with token
4. Token invalidated after use

## OAuth2 Provider Configuration

### Google OAuth2
```yaml
authorization_url: https://accounts.google.com/o/oauth2/v2/auth
token_url: https://oauth2.googleapis.com/token
userinfo_url: https://www.googleapis.com/oauth2/v2/userinfo
scopes:
  - openid
  - email
  - profile
```

### GitHub OAuth2
```yaml
authorization_url: https://github.com/login/oauth/authorize
token_url: https://github.com/login/oauth/access_token
userinfo_url: https://api.github.com/user
scopes:
  - user:email
  - read:user
```

## Database Schema

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- OAuth accounts (linked to users)
CREATE TABLE oauth_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    access_token_encrypted TEXT,
    refresh_token_encrypted TEXT,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, provider_user_id)
);

-- Refresh tokens
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA256
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP,
    ip_address INET,
    user_agent TEXT
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_oauth_accounts_user ON oauth_accounts(user_id);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);
```

## Error Handling

| Error | HTTP Code | Description |
|-------|-----------|-------------|
| INVALID_CREDENTIALS | 401 | Email/password mismatch |
| EMAIL_NOT_VERIFIED | 403 | Account pending verification |
| ACCOUNT_DISABLED | 403 | User is_active = false |
| RATE_LIMIT_EXCEEDED | 429 | Too many requests |
| INVALID_TOKEN | 401 | JWT expired or malformed |
| TOKEN_REVOKED | 401 | Refresh token invalidated |
| EMAIL_EXISTS | 409 | Registration with existing email |
| OAUTH_LINK_FAILED | 400 | OAuth account already linked |

## Dependencies

```python
# Core
pydantic          # Data validation
pyjwt            # JWT handling
bcrypt           # Password hashing
httpx            # OAuth2 HTTP client

# Optional (for production)
redis            # Rate limiting storage
```

## Implementation Notes

1. **Database**: DuckDB for development, PostgreSQL recommended for production
2. **Token Storage**: Use server-side sessions or secure httpOnly cookies if not using localStorage
3. **Email Service**: SMTP or email service integration required
4. **Secrets Management**: OAuth client secrets and JWT signing key must be environment variables
5. **CORS**: Configure appropriately for frontend integration

## Testing Strategy

- Unit tests for password hashing, JWT encode/decode
- Integration tests for full registration/login flow
- OAuth2 mock tests for provider integration
- Security tests for rate limiting, token expiration
- E2E tests for critical user flows
