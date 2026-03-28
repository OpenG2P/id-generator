"""
FastAPI router with all API endpoints.

Endpoints:
  POST /{id_type}/id         - Issue one ID
  GET  /{id_type}/id/validate/{id} - Validate an ID
  GET  /health                 - Health check
  GET  /version                - Service version
"""

import importlib.metadata
import os
from typing import Annotated

from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse

from ..config import get_settings
from ..generator.filters import check_all_filters
from ..pool.issuer import PoolEmptyError, issue_one
from ..pool.manager import try_immediate_replenish
from .schema import make_error_response, make_response

router = APIRouter(prefix="/v1/idgenerator")

# Path parameter types with validation
IdType = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{1,63}$")]
IdParam = Annotated[str, Path(pattern=r"^\d{1,32}$")]


def _get_id_type_config(id_type: str):
    """Get ID type config or None if not configured."""
    settings = get_settings()
    return settings.id_generator.id_types.get(id_type)


# -------------------------------------------------------------------------
# POST /{id_type}/id - Issue ID
# -------------------------------------------------------------------------
@router.post("/{id_type}/id")
async def issue_id(id_type: IdType):
    """Issue a single ID from the specified ID type pool."""
    type_config = _get_id_type_config(id_type)
    if type_config is None:
        return JSONResponse(
            status_code=404,
            content=make_error_response(
                "IDG-003",
                f"Unknown ID type '{id_type}'",
            ),
        )

    # Always try to issue first — there may be AVAILABLE IDs in the pool
    # even if the generation space is exhausted (all valid IDs already
    # generated but not yet taken).
    try:
        id_value = await issue_one(id_type)
        return JSONResponse(
            status_code=200,
            content=make_response({"id": id_value}),
        )
    except PoolEmptyError:
        # Pool is empty — try immediate replenishment (only helps if
        # generation space is not yet exhausted)
        settings = get_settings()
        replenished = await try_immediate_replenish(id_type, settings)

        if not replenished:
            # Generation space is exhausted AND pool is empty
            # = all IDs have been taken
            return JSONResponse(
                status_code=410,
                content=make_error_response(
                    "IDG-002",
                    f"ID space exhausted for ID type '{id_type}'",
                ),
            )

        # Retry after replenishment
        try:
            id_value = await issue_one(id_type)
            return JSONResponse(
                status_code=200,
                content=make_response({"id": id_value}),
            )
        except PoolEmptyError:
            # Still empty after replenishment — temporary issue
            return JSONResponse(
                status_code=503,
                content=make_error_response(
                    "IDG-001",
                    f"No IDs available for ID type '{id_type}'. "
                    f"Replenishment in progress.",
                ),
            )


# -------------------------------------------------------------------------
# GET /{id_type}/id/validate/{id_value} - Validate ID
# -------------------------------------------------------------------------
@router.get("/{id_type}/id/validate/{id_value}")
async def validate_id(id_type: IdType, id_value: IdParam):
    """Validate whether an ID is structurally valid for an ID type."""
    type_config = _get_id_type_config(id_type)
    if type_config is None:
        return JSONResponse(
            status_code=404,
            content=make_error_response(
                "IDG-003",
                f"Unknown ID type '{id_type}'",
            ),
        )

    settings = get_settings()
    filter_config = settings.id_generator.get_filter_config()
    is_valid = check_all_filters(id_value, type_config.id_length, filter_config)

    return JSONResponse(
        status_code=200,
        content=make_response({"id": id_value, "valid": is_valid}),
    )


# -------------------------------------------------------------------------
# GET /health - Health check
# -------------------------------------------------------------------------
@router.get("/health")
async def health():
    """Health check endpoint. Returns 200 if service is healthy."""
    from ..main import is_startup_complete
    from ..db import get_engine

    if not is_startup_complete():
        return JSONResponse(
            status_code=503,
            content=make_error_response(
                "IDG-005", "Service not ready: startup not complete"
            ),
        )

    try:
        from sqlalchemy import text

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content=make_error_response(
                "IDG-006", f"Database health check failed: {e}"
            ),
        )

    return JSONResponse(
        status_code=200,
        content=make_response({"status": "UP"}),
    )


# -------------------------------------------------------------------------
# GET /version - Service version
# -------------------------------------------------------------------------
@router.get("/version")
async def version():
    """Return service version and build metadata."""
    try:
        svc_version = importlib.metadata.version("id-generator")
    except importlib.metadata.PackageNotFoundError:
        svc_version = "0.1.0-dev"

    build_time = os.environ.get("BUILD_TIME", "dev")
    git_commit = os.environ.get("GIT_COMMIT", "dev")

    return JSONResponse(
        status_code=200,
        content=make_response(
            {
                "service_version": svc_version,
                "build_time": build_time,
                "git_commit": git_commit,
            }
        ),
    )


# -------------------------------------------------------------------------
# GET /config - Service configuration (ID types and filter rules)
# -------------------------------------------------------------------------
@router.get("/config")
async def config():
    """Return the active service configuration (ID types, filter rules).

    Useful for tests and diagnostics to discover configured ID types
    without hardcoding names.
    """
    settings = get_settings()
    cfg = settings.id_generator

    id_types = {
        name: {"id_length": ns.id_length}
        for name, ns in cfg.id_types.items()
    }

    return JSONResponse(
        status_code=200,
        content=make_response(
            {
                "id_types": id_types,
                "filter_rules": cfg.get_filter_config(),
            }
        ),
    )
