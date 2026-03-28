"""
Shared fixtures and CLI option registration for ID Generator tests.

All tests are API-level integration tests against a running service.
ID type names are auto-discovered from the service's /config endpoint.
"""

import os

import httpx
import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help="Base URL of the ID Generator service (default: http://localhost:8000)",
    )


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url(request):
    """Service base URL from --base-url option or IDGEN_BASE_URL env var."""
    url = request.config.getoption("--base-url")
    if url is None:
        url = os.environ.get("IDGEN_BASE_URL", "http://localhost:8000")
    return url.rstrip("/")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(base_url):
    """Async HTTP client for the test session."""
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=30.0,
    ) as c:
        yield c


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def service_config(client):
    """Fetch and cache the service configuration (ID types, filter rules).

    All ID-type-dependent tests use this to discover ID type names
    and their id_lengths dynamically.
    """
    resp = await client.get("/v1/idgenerator/config")
    assert resp.status_code == 200, (
        f"Failed to fetch service config: {resp.status_code} {resp.text}"
    )
    data = resp.json()
    return data["response"]


@pytest.fixture(scope="session")
def id_types(service_config):
    """Dict of all configured ID types: {name: {id_length: N}}."""
    return service_config["id_types"]


@pytest.fixture(scope="session")
def id_type_1(id_types):
    """First ID type (smallest id_length, for exhaustive tests).

    Picks the first ID type with the smallest id_length.
    """
    sorted_ns = sorted(id_types.items(), key=lambda x: x[1]["id_length"])
    name = sorted_ns[0][0]
    return name


@pytest.fixture(scope="session")
def id_type_2(id_types, id_type_1):
    """Second ID type (smallest id_length, different from id_type_1).

    Picks the second ID type with the smallest id_length for
    ID type independence testing.
    """
    sorted_ns = sorted(id_types.items(), key=lambda x: x[1]["id_length"])
    for name, _ in sorted_ns:
        if name != id_type_1:
            return name
    pytest.skip("Need at least 2 ID types for this test")


@pytest.fixture(scope="session")
def perf_id_type(id_types, id_type_1, id_type_2):
    """Performance test ID type (largest id_length, large pool).

    Picks the ID type with the largest id_length for performance
    tests that need a large pool that won't exhaust.
    """
    sorted_ns = sorted(
        id_types.items(), key=lambda x: x[1]["id_length"], reverse=True
    )
    name = sorted_ns[0][0]
    return name


@pytest.fixture(scope="session")
def id_type_1_length(id_types, id_type_1):
    """ID length configured for id_type_1."""
    return id_types[id_type_1]["id_length"]


@pytest.fixture(scope="session")
def id_type_2_length(id_types, id_type_2):
    """ID length configured for id_type_2."""
    return id_types[id_type_2]["id_length"]


@pytest.fixture(scope="session")
def perf_id_length(id_types, perf_id_type):
    """ID length configured for perf_id_type."""
    return id_types[perf_id_type]["id_length"]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def service_version(client):
    """
    Fetch and cache service version info at session start.

    Returns a dict with keys: service_version, build_time, git_commit.
    On failure, all values are "unknown".
    """
    try:
        resp = await client.get("/v1/idgenerator/version")
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", {})
    except Exception:
        pass
    return {
        "service_version": "unknown",
        "build_time": "unknown",
        "git_commit": "unknown",
    }


# ---------------------------------------------------------------------------
# Session-scoped ID collectors (populated by exhaustive tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def id_type_1_issued_ids():
    """List of all IDs issued from id_type_1, in issuance order.
    Populated by EXH-001."""
    return []


@pytest.fixture(scope="session")
def id_type_2_issued_ids():
    """List of all IDs issued from id_type_2, in issuance order.
    Populated by EXH-002."""
    return []


@pytest.fixture(scope="session")
def id_type_1_exhausted():
    """Tracks whether id_type_1 has been fully exhausted.
    Set to True by EXH-001."""
    return {"exhausted": False}


@pytest.fixture(scope="session")
def id_type_2_exhausted():
    """Tracks whether id_type_2 has been fully exhausted.
    Set to True by EXH-002."""
    return {"exhausted": False}


# ---------------------------------------------------------------------------
# Helper callable fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def issue_id():
    """
    Callable fixture that issues an ID from an ID type.

    Usage:
        resp = await issue_id(client, "farmer_id")
    """

    async def _issue(cl: httpx.AsyncClient, id_type: str):
        return await cl.post(f"/v1/idgenerator/{id_type}/id")

    return _issue


@pytest.fixture(scope="session")
def validate_id():
    """
    Callable fixture that validates an ID against an ID type.

    Usage:
        resp = await validate_id(client, "farmer_id", "57382")
    """

    async def _validate(
        cl: httpx.AsyncClient, id_type: str, id_value: str
    ):
        return await cl.get(
            f"/v1/idgenerator/{id_type}/id/validate/{id_value}"
        )

    return _validate


@pytest.fixture(scope="session")
def health_check():
    """
    Callable fixture that checks service health.

    Usage:
        resp = await health_check(client)
    """

    async def _health(cl: httpx.AsyncClient):
        return await cl.get("/v1/idgenerator/health")

    return _health
