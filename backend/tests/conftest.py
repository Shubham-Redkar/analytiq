"""Test configuration and shared fixtures for AnalytIQ backend tests."""

import logging
from collections.abc import AsyncGenerator

import pytest
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

# Dedicated test database engine and session factory to protect development data
_test_engine: AsyncEngine | None = None
_test_session_factory: async_sessionmaker[AsyncSession] | None = None
_test_db_initialized = False


async def ensure_test_database_exists() -> None:
    """Ensure the isolated test database (analytiq_test_db) exists on PostgreSQL."""
    settings = get_settings()
    admin_url = (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/postgres"
    )
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            check_sql = text("SELECT 1 FROM pg_database WHERE datname = 'analytiq_test_db'")
            result = await conn.execute(check_sql)
            if not result.scalar():
                await conn.execute(text("CREATE DATABASE analytiq_test_db"))
                logger.info("Created isolated test database: analytiq_test_db")
    except Exception as exc:
        logger.debug("Test database presence check exception: %s", exc)
    finally:
        await admin_engine.dispose()


def get_test_engine() -> AsyncEngine:
    """Return the shared test engine pointing exclusively to analytiq_test_db."""
    global _test_engine
    if _test_engine is None:
        settings = get_settings()
        test_db_url = (
            f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/analytiq_test_db"
        )
        _test_engine = create_async_engine(
            test_db_url,
            pool_pre_ping=True,
            echo=False,
        )
    return _test_engine


def get_test_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory bound to analytiq_test_db."""
    global _test_session_factory
    if _test_session_factory is None:
        _test_session_factory = async_sessionmaker(
            get_test_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _test_session_factory


async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency override yielding a database session bound to the test database."""
    factory = get_test_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Ensure test database schema exists and clean up test tables for isolation.

    Crucially, this operates SOLELY on analytiq_test_db, completely preserving
    the development database (analytiq_db) and user accounts across test runs.
    """
    global _test_db_initialized
    try:
        await ensure_test_database_exists()
        engine = get_test_engine()

        if not _test_db_initialized:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            _test_db_initialized = True

        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE sessions, users RESTART IDENTITY CASCADE"))
    except Exception as exc:
        logger.debug("Test database setup skipped: %s", exc)

    # Override get_db_session in FastAPI app for all test requests
    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional database session from the isolated test database."""
    factory = get_test_session_factory()
    async with factory() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client for the FastAPI application configured with test DB."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost:3000",
        headers={"origin": "http://localhost:3000"},
    ) as ac:
        yield ac
