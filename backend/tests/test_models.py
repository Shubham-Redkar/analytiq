"""Tests for SQLAlchemy models and database constraints."""

import uuid
from datetime import UTC, datetime

from app.models.session import Session
from app.models.user import User


class TestUserAndSessionModels:
    """Test User and Session entity behaviors and relationships."""

    def test_user_instantiation(self) -> None:
        """User model can be instantiated with default and custom values."""
        user = User(
            email="test@analytiq.io",
            password_hash="argon2id_hash_placeholder",
            display_name="Analyst One",
        )
        assert user.email == "test@analytiq.io"
        assert user.password_hash == "argon2id_hash_placeholder"
        assert user.display_name == "Analyst One"
        assert user.is_active is True
        assert user.failed_login_attempts == 0
        assert user.locked_until is None

    def test_session_instantiation(self) -> None:
        """Session model can be instantiated and linked to a user."""
        user_id = uuid.uuid4()
        now = datetime.now(UTC)
        session = Session(
            user_id=user_id,
            token_hash="a" * 64,
            expires_at=now,
        )
        assert session.user_id == user_id
        assert session.token_hash == "a" * 64
        assert session.expires_at == now
        assert session.revoked_at is None
        assert session.ip_address is None

    def test_model_repr(self) -> None:
        """Model string representations contain identifying attributes."""
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="alice@analytiq.io",
            password_hash="hash",
            display_name="Alice",
        )
        assert f"<User id={user_id} email=alice@analytiq.io>" == repr(user)

        session = Session(
            id=user_id,
            user_id=user_id,
            token_hash="b" * 64,
            expires_at=datetime.now(UTC),
        )
        assert f"<Session id={user_id} user_id={user_id}>" == repr(session)
