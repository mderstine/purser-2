---
id: spec-user-authentication-system
title: User Authentication System
created: 2026-03-26
source: /tmp/test-spec.md
---

# User Authentication System

We need a user authentication system that supports email/password login,
OAuth2 with Google and GitHub, and session management with JWT tokens.

The system should handle:
- User registration with email verification
- Login with rate limiting
- Password reset flow
- OAuth2 callback handling
- JWT token issuance and refresh
- Session invalidation
