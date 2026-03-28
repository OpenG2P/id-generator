"""
Database table management for table-per-namespace strategy.

Tables are created dynamically on startup using CREATE TABLE IF NOT EXISTS.
Namespace names are validated to prevent SQL injection.
"""

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Regex for valid namespace names (matches the API path parameter constraint)
_NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def validate_namespace(namespace: str) -> None:
    """Validate a namespace name against the allowed pattern.

    Raises:
        ValueError: If the namespace name is invalid.
    """
    if not _NAMESPACE_PATTERN.match(namespace):
        raise ValueError(
            f"Invalid namespace name '{namespace}'. Must match "
            f"pattern: ^[a-z][a-z0-9_]{{1,63}}$"
        )


def table_name(namespace: str) -> str:
    """Get the table name for a namespace."""
    validate_namespace(namespace)
    return f"id_pool_{namespace}"


async def create_namespace_table(engine: AsyncEngine, namespace: str) -> None:
    """Create the ID pool table and index for a namespace if they
    don't already exist.

    Args:
        engine: The async SQLAlchemy engine.
        namespace: The namespace name (validated).
    """
    validate_namespace(namespace)
    tbl = table_name(namespace)

    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {tbl} (
            id_value    VARCHAR(32)     PRIMARY KEY,
            status      VARCHAR(16)     NOT NULL DEFAULT 'AVAILABLE',
            created_at  TIMESTAMPTZ     NOT NULL DEFAULT now(),
            issued_at   TIMESTAMPTZ     NULL
        )
    """

    create_index_sql = f"""
        CREATE INDEX IF NOT EXISTS idx_{namespace}_available
        ON {tbl} (status) WHERE status = 'AVAILABLE'
    """

    async with engine.begin() as conn:
        await conn.execute(text(create_table_sql))
        await conn.execute(text(create_index_sql))
