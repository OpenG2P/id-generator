"""
Async database engine and session management.

PostgreSQL connection parameters are read from environment variables.
"""

import os

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

_engine: AsyncEngine | None = None


def _build_database_url() -> str:
    """Construct the async PostgreSQL connection URL from env vars."""
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "idgenerator")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


def init_engine() -> AsyncEngine:
    """Initialize the async SQLAlchemy engine."""
    global _engine
    url = _build_database_url()
    _engine = create_async_engine(
        url,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
    )
    return _engine


def get_engine() -> AsyncEngine:
    """Get the current engine. Raises if not initialized."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    return _engine


def get_session() -> AsyncSession:
    """Create a new async session."""
    return AsyncSession(get_engine(), expire_on_commit=False)


async def dispose_engine() -> None:
    """Dispose of the engine and close all connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
