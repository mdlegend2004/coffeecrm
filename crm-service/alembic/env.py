"""
alembic/env.py — Async Alembic migration environment.

Key design:
  - We use run_async_migrations() because our engine is async (asyncpg).
  - DATABASE_URL is read from .env via python-dotenv.
  - The URL is passed directly to create_async_engine (bypassing
    ConfigParser's % interpolation which breaks URL-encoded passwords).
  - All 5 models are imported here so autogenerate detects every table.
"""

import asyncio
import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Load .env so DATABASE_URL is available
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Render provides postgres://… but asyncpg needs postgresql+asyncpg://…
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Alembic Config object — used for logging config only
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base and ALL models so autogenerate detects every table
from app.db.database import Base          # noqa: E402
from app.models.customer import Customer  # noqa: E402, F401
from app.models.order import Order        # noqa: E402, F401
from app.models.segment import Segment    # noqa: E402, F401
from app.models.campaign import Campaign  # noqa: E402, F401
from app.models.communication import Communication  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection needed)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Bind Alembic to an open (sync-wrapped) connection and apply all pending migrations in one transaction."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Build the async engine directly from DATABASE_URL (not via ConfigParser)
    to avoid the % interpolation bug with URL-encoded special characters.
    NullPool ensures no connection reuse during migrations.
    """
    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — wraps async runner in asyncio.run()."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
