"""AnalytIQ API V1 - Authentication endpoints (register, login, logout, me)."""

from typing import Literal

from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUser, DatabaseSession, get_token_from_request, verify_csrf
from app.core.config import get_settings
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserResponse,
)
from app.services.auth import auth_service

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    register_in: RegisterRequest,
    db: DatabaseSession,
) -> UserResponse:
    """Register a new user with email, password, and display name."""
    user = await auth_service.register_user(db, register_in)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=UserResponse,
    summary="Log in and obtain a session cookie",
)
async def login(
    login_in: LoginRequest,
    request: Request,
    response: Response,
    db: DatabaseSession,
) -> UserResponse:
    """Authenticate with email and password, setting an HTTP-only session cookie."""
    settings = get_settings()
    user = await auth_service.authenticate_user(
        db=db,
        email=login_in.email,
        password=login_in.password,
    )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    _, raw_token = await auth_service.create_session(
        db=db,
        user_id=user.id,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    samesite_policy: Literal["lax", "strict", "none"] = "lax"
    if settings.cookie_samesite in ("lax", "strict", "none"):
        samesite_policy = settings.cookie_samesite  # type: ignore[assignment]

    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_expire_days * 86400,
        httponly=True,
        samesite=samesite_policy,
        secure=settings.cookie_secure,
        path="/",
    )

    return UserResponse.model_validate(user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out and revoke current session",
)
async def logout(
    request: Request,
    response: Response,
    db: DatabaseSession,
) -> MessageResponse:
    """Revoke current session and delete the session cookie."""
    settings = get_settings()
    token, source = get_token_from_request(request)

    if source == "cookie":
        verify_csrf(request)

    if token:
        await auth_service.revoke_session(db, token)

    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
    )

    return MessageResponse(message="Successfully logged out.")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: CurrentUser,
) -> UserResponse:
    """Return profile of currently authenticated user."""
    return UserResponse.model_validate(current_user)
