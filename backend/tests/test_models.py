"""Tests for SQLAlchemy models and database constraints."""

import uuid
from datetime import UTC, datetime

from app.models.dataset import Dataset
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

    def test_dataset_instantiation(self) -> None:
        """Dataset model can be instantiated with valid metadata."""
        owner_id = uuid.uuid4()
        dataset = Dataset(
            owner_id=owner_id,
            name="Q4 Sales",
            original_filename="sales_q4.csv",
            file_format="CSV",
            file_size_bytes=10240,
            storage_key="test_storage_key_123",
            status="ready",
            row_count=100,
            column_count=5,
        )
        assert dataset.owner_id == owner_id
        assert dataset.name == "Q4 Sales"
        assert dataset.file_format == "CSV"
        assert dataset.file_size_bytes == 10240
        assert dataset.storage_key == "test_storage_key_123"
        assert dataset.status == "ready"
        assert dataset.row_count == 100
        assert dataset.column_count == 5
        assert repr(dataset) == (
            f"<Dataset(id={dataset.id}, name='Q4 Sales', format=CSV, status=ready)>"
        )
