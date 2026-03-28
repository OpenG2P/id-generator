"""
ID issuance logic.

Fetches one AVAILABLE ID from the pool and marks it as TAKEN using
SELECT ... FOR UPDATE SKIP LOCKED for zero-contention concurrency.
"""

from sqlalchemy import text

from ..db import get_session
from ..models import table_name


class PoolEmptyError(Exception):
    """Raised when no AVAILABLE IDs exist in the pool."""

    pass


async def issue_one(namespace: str) -> str:
    """Issue a single ID from the namespace pool.

    Atomically selects an available ID and marks it as TAKEN.
    Uses FOR UPDATE SKIP LOCKED for zero contention between pods.

    Args:
        namespace: The namespace to issue from.

    Returns:
        The issued ID string.

    Raises:
        PoolEmptyError: If no AVAILABLE IDs are in the pool.
    """
    tbl = table_name(namespace)

    select_sql = text(f"""
        SELECT id_value FROM {tbl}
        WHERE status = 'AVAILABLE'
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    """)

    update_sql = text(f"""
        UPDATE {tbl}
        SET status = 'TAKEN', issued_at = now()
        WHERE id_value = :id_value
    """)

    async with get_session() as session:
        async with session.begin():
            result = await session.execute(select_sql)
            row = result.fetchone()

            if row is None:
                raise PoolEmptyError(
                    f"No available IDs in namespace '{namespace}'"
                )

            id_value = row[0]
            await session.execute(update_sql, {"id_value": id_value})

    return id_value
