"""
Pool replenishment manager.

Handles background pool filling, startup blocking, advisory lock
coordination across pods, and exhaustion detection.
"""

import asyncio
import logging
import zlib

from sqlalchemy import text

from ..config import Settings
from ..db import get_engine, get_session
from ..generator.engine import generate_batch
from ..models import table_name

logger = logging.getLogger(__name__)

# Per-ID-type exhaustion tracking
_exhausted: dict[str, bool] = {}


def is_exhausted(id_type: str) -> bool:
    """Check if an ID type's space is exhausted."""
    return _exhausted.get(id_type, False)


def _advisory_lock_key(id_type: str) -> int:
    """Generate a consistent advisory lock key for an ID type.

    Uses CRC32 to convert the ID type string to a 32-bit integer,
    which PostgreSQL accepts as an advisory lock key.
    """
    return zlib.crc32(id_type.encode()) & 0x7FFFFFFF


async def count_available(id_type: str) -> int:
    """Count AVAILABLE IDs in an ID type's pool."""
    tbl = table_name(id_type)
    sql = text(f"SELECT COUNT(*) FROM {tbl} WHERE status = 'AVAILABLE'")

    async with get_session() as session:
        result = await session.execute(sql)
        return result.scalar_one()


async def _insert_batch(id_type: str, ids: list[str]) -> int:
    """Insert a batch of IDs into the pool, skipping duplicates.

    Inserts in small sub-batches (100 rows per transaction) to avoid
    holding long-running locks that can cause deadlocks with concurrent
    issue requests.

    Args:
        id_type: Target ID type.
        ids: List of ID strings to insert.

    Returns:
        Number of IDs actually inserted (excluding duplicates).
    """
    if not ids:
        return 0

    tbl = table_name(id_type)
    inserted = 0
    chunk_size = 100

    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        async with get_session() as session:
            async with session.begin():
                for id_val in chunk:
                    result = await session.execute(
                        text(
                            f"INSERT INTO {tbl} (id_value) VALUES (:id_val) "
                            f"ON CONFLICT DO NOTHING"
                        ),
                        {"id_val": id_val},
                    )
                    inserted += result.rowcount

    return inserted


async def fill_pool(id_type: str, settings: Settings) -> None:
    """Fill the pool for an ID type up to the configured batch size.

    Generates IDs in sub-batches and inserts them. Stops early if
    the ID space is exhausted.

    Args:
        id_type: Target ID type.
        settings: Application settings.
    """
    cfg = settings.id_generator
    type_config = cfg.id_types[id_type]
    id_length = type_config.id_length
    filter_config = cfg.get_filter_config()

    target = cfg.pool_generation_batch_size
    sub_batch_size = cfg.sub_batch_size
    generated = 0

    while generated < target:
        batch_target = min(sub_batch_size, target - generated)

        ids, exhausted = generate_batch(
            count=batch_target,
            id_length=id_length,
            config=filter_config,
            max_attempts=cfg.exhaustion_max_attempts,
        )

        if ids:
            inserted = await _insert_batch(id_type, ids)
            # Track by number of IDs we attempted (not just inserted)
            # to avoid infinite looping when most IDs are duplicates
            generated += len(ids)
            logger.info(
                "ID type '%s': generated %d, inserted %d "
                "(batch progress: %d/%d)",
                id_type,
                len(ids),
                inserted,
                generated,
                target,
            )

        if exhausted:
            _exhausted[id_type] = True
            logger.warning(
                "ID type '%s': ID space exhausted after generating %d IDs",
                id_type,
                generated,
            )
            break


async def try_immediate_replenish(id_type: str, settings: Settings) -> bool:
    """Attempt immediate replenishment when pool is empty during an
    issue request.

    Args:
        id_type: Target ID type.
        settings: Application settings.

    Returns:
        True if at least one new ID was generated, False if space
        is exhausted.
    """
    if is_exhausted(id_type):
        return False

    cfg = settings.id_generator
    type_config = cfg.id_types[id_type]
    filter_config = cfg.get_filter_config()

    ids, exhausted = generate_batch(
        count=100,  # Small batch for immediate response
        id_length=type_config.id_length,
        config=filter_config,
        max_attempts=cfg.exhaustion_max_attempts,
    )

    if ids:
        inserted = await _insert_batch(id_type, ids)
        if inserted > 0:
            return True
        # All generated IDs already exist in DB — space is effectively
        # exhausted even though in-memory generation succeeded.
        logger.warning(
            "ID type '%s': generated %d IDs but 0 were new "
            "(all already exist in DB). Space is exhausted.",
            id_type,
            len(ids),
        )
        _exhausted[id_type] = True
        return False

    if exhausted:
        _exhausted[id_type] = True

    return False


async def ensure_minimum_pool(id_type: str, settings: Settings) -> None:
    """Ensure an ID type has at least pool_min_threshold AVAILABLE IDs.

    Called at startup (blocking). Generates IDs until the threshold is met
    or the space is exhausted.
    """
    cfg = settings.id_generator
    threshold = cfg.pool_min_threshold

    available = await count_available(id_type)
    logger.info(
        "ID type '%s': %d AVAILABLE IDs (threshold: %d)",
        id_type,
        available,
        threshold,
    )

    while available < threshold and not is_exhausted(id_type):
        await fill_pool(id_type, settings)
        available = await count_available(id_type)

    if is_exhausted(id_type):
        logger.warning(
            "ID type '%s': space exhausted with %d AVAILABLE IDs "
            "(threshold was %d)",
            id_type,
            available,
            threshold,
        )
    else:
        logger.info(
            "ID type '%s': pool ready with %d AVAILABLE IDs",
            id_type,
            available,
        )


async def check_and_replenish(id_type: str, settings: Settings) -> None:
    """Check pool level and replenish if below threshold.

    Uses PostgreSQL advisory locks to ensure only one pod generates
    at a time per ID type. The lock is held on a single session
    throughout the entire generation process.
    """
    if is_exhausted(id_type):
        return

    cfg = settings.id_generator
    available = await count_available(id_type)

    if available >= cfg.pool_min_threshold:
        return

    lock_key = _advisory_lock_key(id_type)

    # Use a single session for the entire lock lifecycle:
    # acquire lock -> fill pool -> release lock
    async with get_session() as session:
        # Try to acquire advisory lock (non-blocking)
        result = await session.execute(
            text(f"SELECT pg_try_advisory_lock({lock_key})")
        )
        acquired = result.scalar_one()

        if not acquired:
            logger.debug(
                "ID type '%s': advisory lock not acquired, "
                "another pod is generating",
                id_type,
            )
            return

        try:
            logger.info(
                "ID type '%s': pool below threshold (%d < %d), "
                "starting replenishment",
                id_type,
                available,
                cfg.pool_min_threshold,
            )
            await fill_pool(id_type, settings)
        finally:
            # Release the advisory lock on the SAME session
            await session.execute(
                text(f"SELECT pg_advisory_unlock({lock_key})")
            )


async def pool_replenishment_loop(settings: Settings) -> None:
    """Background loop that periodically checks and replenishes all
    ID type pools.

    Runs indefinitely until cancelled.
    """
    interval = settings.id_generator.pool_check_interval_seconds

    while True:
        await asyncio.sleep(interval)

        for id_type in settings.id_generator.id_types:
            try:
                await check_and_replenish(id_type, settings)
            except Exception:
                logger.exception(
                    "Error during pool replenishment for ID type '%s'",
                    id_type,
                )
