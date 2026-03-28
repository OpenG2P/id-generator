"""
FastAPI application entry point.

Manages the application lifespan:
  - Startup: DB init, table creation, pool filling (blocking), background task
  - Shutdown: Cancel background task, dispose DB engine
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.router import router
from .config import get_settings
from .db import dispose_engine, init_engine
from .models import create_namespace_table
from .pool.manager import ensure_minimum_pool, pool_replenishment_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_startup_complete = False
_background_task: asyncio.Task | None = None


def is_startup_complete() -> bool:
    """Check if the service has completed startup initialization."""
    return _startup_complete


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    global _startup_complete, _background_task

    settings = get_settings()

    # 1. Initialize database engine
    logger.info("Initializing database engine...")
    engine = init_engine()

    # 2. Create tables and fill pools for each namespace
    for namespace, ns_config in settings.id_generator.namespaces.items():
        logger.info(
            "Setting up namespace '%s' (id_length=%d)...",
            namespace,
            ns_config.id_length,
        )

        # Create table and index if they don't exist
        await create_namespace_table(engine, namespace)

        # Fill pool to minimum threshold (blocking)
        await ensure_minimum_pool(namespace, settings)

    # 3. Mark startup complete (health endpoint returns 200)
    _startup_complete = True
    logger.info("Startup complete. All namespace pools are ready.")

    # 4. Start background replenishment loop
    _background_task = asyncio.create_task(
        pool_replenishment_loop(settings)
    )
    logger.info(
        "Background pool replenishment started (interval: %ds)",
        settings.id_generator.pool_check_interval_seconds,
    )

    yield

    # Shutdown
    logger.info("Shutting down...")

    if _background_task is not None:
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            pass

    await dispose_engine()
    _startup_complete = False
    logger.info("Shutdown complete.")


# Create the FastAPI application
app = FastAPI(
    title="ID Generator",
    description="Unique numeric ID generator service with multi-namespace support",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
