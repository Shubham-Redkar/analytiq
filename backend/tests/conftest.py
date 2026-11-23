"""Test configuration and shared fixtures for AnalytIQ backend tests."""

import logging
from collections.abc import AsyncGenerator

import pytest
from app.db.base import Base
from app.db.session import get_engine, get_session_factory
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_db_initialized = False


@pytest.fixture(autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Ensure database schema exists and clean up tables for test isolation."""
    global _db_initialized
    try:
        engine = get_engine()
        if not _db_initialized:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            _db_initialized = True

        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE sessions, users RESTART IDENTITY CASCADE"))
    except Exception as exc:
        logger.debug("Test database setup skipped: %s", exc)
    yield


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional database session for tests."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client for the FastAPI application."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost:3000",
        headers={"origin": "http://localhost:3000"},
    ) as ac:
        yield ac
