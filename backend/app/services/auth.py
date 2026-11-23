"""AnalytIQ Services - Authentication and session management service."""

import logging
import uuid
from datetime import timedelta

from app.core.config import get_settings
from app.core.security import (
    dummy_verify_password,
    generate_session_token,
    hash_password,
    hash_session_token,
    utc_now,
    verify_password,
)
from app.models.session import Session
from app.models.user import User
from app.schemas.auth import RegisterRequest
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


class AuthService:
    """Service providing user authentication, registration, and session management."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def register_user(
        self,
        db: AsyncSession,
        register_in: RegisterRequest,
    ) -> User:
        """Register a new user account with normalized email and Argon2id password hashing.

        Raises HTTPException 409 if email already exists.
        """
        normalized_email = register_in.email.strip().lower()

        # Check for existing user with identical email
        stmt = select(User).where(User.email == normalized_email)
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists.",
            )

        password_hash = hash_password(register_in.password)
        user = User(
            email=normalized_email,
            password_hash=password_hash,
            display_name=register_in.display_name.strip(),
            is_active=True,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info("User registered successfully: id=%s email=%s", user.id, user.email)
        return user

    async def authenticate_user(
        self,
        db: AsyncSession,
        email: str,
        password: str,
    ) -> User:
        """Authenticate user by email and password with lockout protection and timing safety.

        Raises HTTPException 401 on bad credentials, 423 on locked account, 403 on disabled.
        """
        normalized_email = email.strip().lower()
        stmt = select(User).where(User.email == normalized_email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            # Prevent timing attacks via dummy verification
            dummy_verify_password(password)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        now = utc_now()

        # Check account lockout status
        if user.locked_until is not None:
            if user.locked_until > now:
                logger.warning("Authentication rejected: account locked user_id=%s", user.id)
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=(
                        "Account is temporarily locked due to multiple failed login attempts. "
                        "Please try again later."
                    ),
                )
            # Lockout period expired; reset attempt counter
            user.failed_login_attempts = 0
            user.locked_until = None

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive.",
            )

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= self.settings.max_login_attempts:
                user.locked_until = now + timedelta(minutes=self.settings.lockout_duration_minutes)
                logger.warning(
                    "User account locked after %s failed attempts: id=%s",
                    user.failed_login_attempts,
                    user.id,
                )
            # Commit failure count even before raising exception
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        # Successful login: reset failed attempts
        if user.failed_login_attempts > 0 or user.locked_until is not None:
            user.failed_login_attempts = 0
            user.locked_until = None
            await db.flush()

        logger.info("User authenticated successfully: id=%s", user.id)
        return user

    async def create_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Session, str]:
        """Create a new session record and return the session along with raw opaque token."""
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        now = utc_now()
        expires_at = now + timedelta(days=self.settings.session_expire_days)

        session = Session(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address[:45] if ip_address else None,
            user_agent=user_agent[:512] if user_agent else None,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session, raw_token

    async def revoke_session(
        self,
        db: AsyncSession,
        raw_token: str,
    ) -> bool:
        """Revoke an active session by token hash."""
        token_hash = hash_session_token(raw_token)
        stmt = select(Session).where(
            Session.token_hash == token_hash,
            Session.revoked_at.is_(None),
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if session is not None:
            session.revoked_at = utc_now()
            await db.flush()
            return True
        return False

    async def get_user_from_token(
        self,
        db: AsyncSession,
        raw_token: str,
    ) -> User | None:
        """Retrieve active user associated with valid, unrevoked, unexpired session token."""
        token_hash = hash_session_token(raw_token)
        now = utc_now()
        stmt = (
            select(Session)
            .options(selectinload(Session.user))
            .where(
                Session.token_hash == token_hash,
                Session.revoked_at.is_(None),
                Session.expires_at > now,
            )
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if session is not None and session.user is not None and session.user.is_active:
            return session.user
        return None


auth_service = AuthService()
