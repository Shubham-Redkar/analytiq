"""Alembic migration environment - configured to use AnalytIQ application settings.

The database URL is loaded from the centralized Pydantic Settings object so that
no credentials are hardcoded in Alembic configuration files. Migrations run
asynchronously using SQLAlchemy 2.x and asyncpg.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ---------------------------------------------------------------------------
# Ensure the backend package is importable when Alembic is invoked from the
# backend/ directory (the normal working directory).
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import get_settings

# Alembic Config object - provides access to values within alembic.ini.
config = context.config

# Configure logging from the ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url with the value from application settings.
_settings = get_settings()
config.set_main_option("sqlalchemy.url", _settings.database_url)

# ---------------------------------------------------------------------------
# SQLAlchemy MetaData for autogenerate support.
# Import your declarative Base here once models exist, e.g.:
#   from app.db.base import Base
#   target_metadata = Base.metadata
# ---------------------------------------------------------------------------
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Useful for generating SQL scripts without a live database connection.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations within an active database connection context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations asynchronously using SQLAlchemy's async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an active database connection."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
