"""
ID issuance logic.

Fetches one AVAILABLE ID from the pool and marks it as TAKEN using
SELECT ... FOR UPDATE SKIP LOCKED for zero-contention concurrency.

Includes retry logic for transient database errors (e.g., deadlocks).
"""

import asyncio
import logging

from sqlalchemy import text

from ..db import get_session
from ..models import table_name

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 0.1


class PoolEmptyError(Exception):
    """Raised when no AVAILABLE IDs exist in the pool."""

    pass


async def issue_one(namespace: str) -> str:
    """Issue a single ID from the namespace pool.

    Atomically selects an available ID and marks it as TAKEN.
    Uses FOR UPDATE SKIP LOCKED for zero contention between pods.

    Retries up to MAX_RETRIES times on transient database errors
    (e.g., deadlocks).

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

    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
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

        except PoolEmptyError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(
                "Namespace '%s': issue attempt %d/%d failed: %s",
                namespace,
                attempt + 1,
                MAX_RETRIES,
                e,
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    raise last_error
