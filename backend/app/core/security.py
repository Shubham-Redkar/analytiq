"""AnalytIQ Core - Cryptographic security and password hashing utilities."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

logger = logging.getLogger(__name__)

# Argon2id password hasher with secure defaults
_hasher = PasswordHasher()

# Precomputed valid argon2id hash for dummy verification to prevent timing discrepancies
_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$OwFmJp9VFMBnvMz6XYthbA$vQgoRgLhXgyYKl1KM4qLrjo3RWChLT1FrflNhUR2pdA"  # noqa: E501


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash without timing leaks."""
    try:
        return _hasher.verify(hashed_password, password)
    except (VerifyMismatchError, Exception):
        return False


def dummy_verify_password(password: str) -> None:
    """Perform dummy verification to prevent user enumeration via timing discrepancies."""
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except Exception as exc:
        logger.debug("Dummy verification swallowed mismatch: %s", exc)


def generate_session_token() -> str:
    """Generate a high-entropy cryptographically secure opaque session token."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Hash an opaque session token using SHA-256 for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(UTC)
