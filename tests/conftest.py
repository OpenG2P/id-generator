"""
Shared fixtures and CLI option registration for ID Generator tests.

All tests are API-level integration tests against a running service.
"""

import os

import httpx
import pytest


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
    parser.addoption(
        "--namespace-1",
        action="store",
        default=None,
        help="First test namespace (default: test_ns_1)",
    )
    parser.addoption(
        "--namespace-2",
        action="store",
        default=None,
        help="Second test namespace (default: test_ns_2)",
    )
    parser.addoption(
        "--perf-namespace",
        action="store",
        default=None,
        help="Performance test namespace (default: test_perf_ns)",
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


@pytest.fixture(scope="session")
def namespace_1(request):
    """First test namespace (length=5, for exhaustive tests)."""
    ns = request.config.getoption("--namespace-1")
    if ns is None:
        ns = os.environ.get("IDGEN_TEST_NAMESPACE_1", "test_ns_1")
    return ns


@pytest.fixture(scope="session")
def namespace_2(request):
    """Second test namespace (length=5, for exhaustive tests)."""
    ns = request.config.getoption("--namespace-2")
    if ns is None:
        ns = os.environ.get("IDGEN_TEST_NAMESPACE_2", "test_ns_2")
    return ns


@pytest.fixture(scope="session")
def perf_namespace(request):
    """Performance test namespace (length=10, large pool)."""
    ns = request.config.getoption("--perf-namespace")
    if ns is None:
        ns = os.environ.get("IDGEN_TEST_PERF_NAMESPACE", "test_perf_ns")
    return ns


@pytest.fixture(scope="session")
async def client(base_url):
    """Async HTTP client for the test session."""
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=30.0,
    ) as c:
        yield c


@pytest.fixture(scope="session")
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
def ns1_issued_ids():
    """List of all IDs issued from namespace_1, in issuance order.
    Populated by EXH-001."""
    return []


@pytest.fixture(scope="session")
def ns2_issued_ids():
    """List of all IDs issued from namespace_2, in issuance order.
    Populated by EXH-002."""
    return []


@pytest.fixture(scope="session")
def ns1_exhausted():
    """Tracks whether namespace_1 has been fully exhausted.
    Set to True by EXH-001."""
    return {"exhausted": False}


@pytest.fixture(scope="session")
def ns2_exhausted():
    """Tracks whether namespace_2 has been fully exhausted.
    Set to True by EXH-002."""
    return {"exhausted": False}


# ---------------------------------------------------------------------------
# Helper callable fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def issue_id():
    """
    Callable fixture that issues an ID from a namespace.

    Usage:
        resp = await issue_id(client, "test_ns_1")
    """

    async def _issue(cl: httpx.AsyncClient, namespace: str):
        return await cl.post(f"/v1/idgenerator/{namespace}/id")

    return _issue


@pytest.fixture(scope="session")
def validate_id():
    """
    Callable fixture that validates an ID against a namespace.

    Usage:
        resp = await validate_id(client, "test_ns_1", "57382")
    """

    async def _validate(
        cl: httpx.AsyncClient, namespace: str, id_value: str
    ):
        return await cl.get(
            f"/v1/idgenerator/{namespace}/id/validate/{id_value}"
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
