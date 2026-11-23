"""Tests for cryptographic security and hashing utilities."""

from datetime import UTC

from app.core.security import (
    dummy_verify_password,
    generate_session_token,
    hash_password,
    hash_session_token,
    utc_now,
    verify_password,
)


class TestSecurityUtilities:
    """Unit tests for app.core.security."""

    def test_hash_and_verify_password(self) -> None:
        """Argon2id produces valid hash and verifies plaintext match."""
        password = "SecurePassword123!"
        hashed = hash_password(password)

        assert hashed.startswith("$argon2id$")
        assert verify_password(password, hashed) is True

    def test_verify_password_mismatch(self) -> None:
        """Argon2id verification returns False for incorrect password."""
        password = "SecurePassword123!"
        hashed = hash_password(password)

        assert verify_password("WrongPassword!", hashed) is False

    def test_dummy_verify_password(self) -> None:
        """dummy_verify_password executes without raising exceptions."""
        dummy_verify_password("AnyPassword")

    def test_generate_session_token(self) -> None:
        """Token generator returns unique, high-entropy urlsafe string."""
        token1 = generate_session_token()
        token2 = generate_session_token()

        assert len(token1) >= 40
        assert token1 != token2

    def test_hash_session_token(self) -> None:
        """Session token hash produces deterministic 64-char SHA-256 hex string."""
        token = "test-token-value-12345"
        hash1 = hash_session_token(token)
        hash2 = hash_session_token(token)

        assert len(hash1) == 64
        assert hash1 == hash2

    def test_utc_now(self) -> None:
        """utc_now returns timezone-aware UTC datetime."""
        now = utc_now()
        assert now.tzinfo is not None
        assert now.tzinfo == UTC
