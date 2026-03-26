"""FastAPI routes for email/password authentication."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from purser.auth.models import TokenResponse, UserCreate, UserLogin, UserResponse
from purser.auth.service import AuthenticationError, AuthService, RateLimitExceededError


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class VerificationRequest(BaseModel):
    """Email verification request."""

    token: str


class ResendVerificationRequest(BaseModel):
    """Resend verification email request."""

    email: EmailStr


class PasswordResetRequest(BaseModel):
    """Password reset initiation request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation request."""

    token: str
    new_password: str = Field(..., min_length=8)


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request."""

    refresh_token: str


def get_auth_service() -> Generator[AuthService, None, None]:
    """Dependency to get auth service instance."""
    service = AuthService()
    try:
        yield service
    finally:
        service.close()


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_current_user_dependency(
    authorization: str | None = Header(None),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Dependency to get current authenticated user.

    Extracts and validates the access token from the Authorization header.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    try:
        return auth_service.get_current_user(token)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def get_current_user() -> Callable[..., UserResponse]:
    """Factory for current user dependency."""
    return Depends(get_current_user_dependency)


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """Register a new user account.

    Creates a new user with email and password. A verification email
    should be sent (token returned in response for testing purposes).
    """
    ip_address = get_client_ip(request)

    try:
        user, verification_token = auth_service.register_user(user_data, ip_address)
    except RateLimitExceededError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        ) from e

    return {
        "user_id": str(user.id),
        "email": user.email,
        "message": "Verification email sent. Please check your inbox.",
        # In production, don't return the token - send via email
        "verification_token": verification_token,  # For testing only
    }


@router.post("/verify", response_model=UserResponse)
async def verify_email(
    request: VerificationRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Verify user email address.

    Validates the verification token and activates the user account.
    """
    try:
        return auth_service.verify_email(request.token)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from e


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    request: ResendVerificationRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Resend verification email.

    Sends a new verification email to the specified address if
    the user exists and is not yet verified.
    """
    token = auth_service.resend_verification(request.email)

    # Always return success to prevent email enumeration
    if token:
        # In production, send email here
        pass

    return MessageResponse(
        message="If the email exists and is not verified, a verification email has been sent."
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    request: Request,
    user_agent: str | None = Header(None),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticate user and get tokens.

    Returns access and refresh tokens upon successful authentication.
    Rate limited to 10 attempts per 15 minutes.
    """
    ip_address = get_client_ip(request)

    try:
        return auth_service.login(login_data, ip_address, user_agent)
    except RateLimitExceededError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )
    except AuthenticationError as e:
        status_code = (
            status.HTTP_403_FORBIDDEN
            if e.code in ("EMAIL_NOT_VERIFIED", "ACCOUNT_DISABLED")
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(status_code=status_code, detail=e.message) from e


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Refresh access token.

    Uses a valid refresh token to get a new access token and refresh token pair.
    Implements token rotation for security.
    """
    try:
        return auth_service.refresh_token(request.refresh_token)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
        ) from e


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: LogoutRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Logout user.

    Revokes the refresh token, invalidating the session.
    """
    auth_service.logout(request.refresh_token)
    return MessageResponse(message="Successfully logged out")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    current_user: UserResponse = Depends(get_current_user_dependency),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Logout from all sessions.

    Revokes all refresh tokens for the current user.
    """
    auth_service.logout_all(current_user.id)
    return MessageResponse(message="Logged out from all sessions")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: PasswordResetRequest,
    request_obj: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Initiate password reset.

    Sends a password reset email to the specified address if
    the user exists. Rate limited to 3 attempts per hour.
    """
    ip_address = get_client_ip(request_obj)

    try:
        token = auth_service.initiate_password_reset(request.email, ip_address)
    except RateLimitExceededError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )

    # Always return success to prevent email enumeration
    if token:
        # In production, send email here
        pass

    return MessageResponse(message="If the email exists, a password reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: PasswordResetConfirm,
    request_obj: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Complete password reset.

    Resets the password using the token from the reset email.
    Rate limited to 10 attempts per 15 minutes.
    """
    ip_address = get_client_ip(request_obj)

    try:
        auth_service.reset_password(request.token, request.new_password, ip_address)
    except RateLimitExceededError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from e

    return MessageResponse(
        message="Password reset successful. Please log in with your new password."
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user_dependency),
) -> UserResponse:
    """Get current user information.

    Returns the profile information for the authenticated user.
    """
    return current_user


@router.get("/sessions", response_model=list[dict[str, Any]])
async def list_user_sessions(
    auth_service: AuthService = Depends(get_auth_service),
    current_user: UserResponse = Depends(get_current_user_dependency),
) -> list[dict[str, Any]]:
    """List active sessions.

    Returns all active sessions for the current user.
    """
    return auth_service.list_sessions(current_user.id)
