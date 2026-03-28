"""
Database table management for table-per-id-type strategy.

Tables are created dynamically on startup using CREATE TABLE IF NOT EXISTS.
ID type names are validated to prevent SQL injection.
"""

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Regex for valid ID type names (matches the API path parameter constraint)
_ID_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def validate_id_type(id_type: str) -> None:
    """Validate an ID type name against the allowed pattern.

    Raises:
        ValueError: If the ID type name is invalid.
    """
    if not _ID_TYPE_PATTERN.match(id_type):
        raise ValueError(
            f"Invalid ID type name '{id_type}'. Must match "
            f"pattern: ^[a-z][a-z0-9_]{{1,63}}$"
        )


def table_name(id_type: str) -> str:
    """Get the table name for an ID type."""
    validate_id_type(id_type)
    return f"id_pool_{id_type}"


async def create_id_type_table(engine: AsyncEngine, id_type: str) -> None:
    """Create the ID pool table and index for an ID type if they
    don't already exist.

    Args:
        engine: The async SQLAlchemy engine.
        id_type: The ID type name (validated).
    """
    validate_id_type(id_type)
    tbl = table_name(id_type)

    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {tbl} (
            id_value    VARCHAR(32)     PRIMARY KEY,
            status      VARCHAR(16)     NOT NULL DEFAULT 'AVAILABLE',
            created_at  TIMESTAMPTZ     NOT NULL DEFAULT now(),
            issued_at   TIMESTAMPTZ     NULL
        )
    """

    create_index_sql = f"""
        CREATE INDEX IF NOT EXISTS idx_{id_type}_available
        ON {tbl} (status) WHERE status = 'AVAILABLE'
    """

    async with engine.begin() as conn:
        await conn.execute(text(create_table_sql))
        await conn.execute(text(create_index_sql))
