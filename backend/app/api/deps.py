"""AnalytIQ API - Request dependencies for authentication, database, and CSRF protection."""

import logging
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.user import User
from app.services.auth import auth_service

logger = logging.getLogger(__name__)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_token_from_request(request: Request) -> tuple[str | None, str]:
    """Extract session token from cookie or Authorization Bearer header.

    Returns (token, source) where source is 'cookie', 'bearer', or 'none'.
    """
    settings = get_settings()
    cookie_token = request.cookies.get(settings.session_cookie_name)
    if cookie_token:
        return cookie_token, "cookie"

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            return token, "bearer"

    return None, "none"


def verify_csrf(request: Request) -> None:
    """CSRF origin verification for state-changing requests authenticated via cookies.

    If request method is state-changing (POST, PUT, PATCH, DELETE) and session cookie is present,
    the Origin or Referer header must match an allowed origin or the request host.
    """
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return

    settings = get_settings()
    if settings.session_cookie_name not in request.cookies:
        # If no session cookie, non-cookie requests are not vulnerable to browser CSRF
        return

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")

    caller_origin: str | None = None
    if origin:
        caller_origin = origin.rstrip("/")
    elif referer:
        parsed = urlparse(referer)
        caller_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    if not caller_origin:
        logger.warning("CSRF check failed: Missing Origin and Referer on state-changing request")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed: missing origin.",
        )

    # Allowed origins: configured CORS origins and server host/netloc
    allowed = {o.rstrip("/") for o in settings.cors_origins}
    host = request.headers.get("host")
    if host:
        allowed.add(f"http://{host}".rstrip("/"))
        allowed.add(f"https://{host}".rstrip("/"))

    if caller_origin not in allowed:
        logger.warning(
            "CSRF check failed: origin '%s' not in allowed origins: %s",
            caller_origin,
            allowed,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed: untrusted origin.",
        )


async def get_current_user(
    request: Request,
    db: DatabaseSession,
) -> User:
    """Dependency that resolves the authenticated user from session token.

    Enforces authentication and active user status.
    """
    token, source = get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # If authenticated via cookie on state-changing method, verify CSRF
    if source == "cookie":
        verify_csrf(request)

    user = await auth_service.get_user_from_token(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
