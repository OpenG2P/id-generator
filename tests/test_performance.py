"""
Category 4: Response Time Tests (PRF-001 through PRF-004)

Measure API response latency. Run against the perf ID type (length=10,
large pool) which should NOT be exhausted during testing.

Performance thresholds are configurable and intentionally generous
to avoid flaky tests across different environments.
"""

import asyncio
import time

import pytest

pytestmark = [
    pytest.mark.performance,
    pytest.mark.order(5),
    pytest.mark.asyncio(loop_scope="session"),
]

# Default performance thresholds (seconds)
# These are generous; tighten per environment as needed.
ISSUE_P50_THRESHOLD = 0.100  # 100ms
ISSUE_P95_THRESHOLD = 0.500  # 500ms
ISSUE_P99_THRESHOLD = 1.000  # 1000ms
VALIDATE_P50_THRESHOLD = 0.050  # 50ms
VALIDATE_P95_THRESHOLD = 0.200  # 200ms
HEALTH_P95_THRESHOLD = 0.200  # 200ms
CONCURRENT_TOTAL_THRESHOLD = 5.0  # 5s for 50 concurrent requests


def _percentile(sorted_values: list[float], p: float) -> float:
    """Calculate the p-th percentile from a sorted list."""
    if not sorted_values:
        return 0.0
    idx = int(len(sorted_values) * p / 100.0)
    idx = min(idx, len(sorted_values) - 1)
    return sorted_values[idx]


# -------------------------------------------------------------------------
# PRF-001: Issue ID response time (sequential)
# -------------------------------------------------------------------------
class TestPRF001:
    """Issue 100 IDs sequentially and verify response time percentiles."""

    async def test_issue_id_response_time(
        self, client, perf_id_type, issue_id
    ):
        durations = []

        for _ in range(100):
            start = time.perf_counter()
            resp = await issue_id(client, perf_id_type)
            elapsed = time.perf_counter() - start

            assert resp.status_code == 200, (
                f"Issue failed with status {resp.status_code}"
            )
            durations.append(elapsed)

        durations.sort()
        p50 = _percentile(durations, 50)
        p95 = _percentile(durations, 95)
        p99 = _percentile(durations, 99)

        print(f"\n  Issue ID latency (n=100):")
        print(f"    p50={p50*1000:.1f}ms  p95={p95*1000:.1f}ms  "
              f"p99={p99*1000:.1f}ms")
        print(f"    min={min(durations)*1000:.1f}ms  "
              f"max={max(durations)*1000:.1f}ms")

        assert p50 < ISSUE_P50_THRESHOLD, (
            f"p50 latency {p50*1000:.1f}ms exceeds "
            f"{ISSUE_P50_THRESHOLD*1000:.0f}ms threshold"
        )
        assert p95 < ISSUE_P95_THRESHOLD, (
            f"p95 latency {p95*1000:.1f}ms exceeds "
            f"{ISSUE_P95_THRESHOLD*1000:.0f}ms threshold"
        )
        assert p99 < ISSUE_P99_THRESHOLD, (
            f"p99 latency {p99*1000:.1f}ms exceeds "
            f"{ISSUE_P99_THRESHOLD*1000:.0f}ms threshold"
        )


# -------------------------------------------------------------------------
# PRF-002: Issue ID concurrent response time
# -------------------------------------------------------------------------
class TestPRF002:
    """Issue 50 IDs concurrently and verify total wall-clock time."""

    async def test_issue_id_concurrent_response_time(
        self, client, perf_id_type, issue_id
    ):
        async def _issue_one():
            resp = await issue_id(client, perf_id_type)
            assert resp.status_code == 200
            return resp

        start = time.perf_counter()
        results = await asyncio.gather(
            *[_issue_one() for _ in range(50)]
        )
        total_time = time.perf_counter() - start

        print(f"\n  Concurrent issue (n=50): "
              f"total={total_time*1000:.1f}ms")

        assert len(results) == 50
        assert total_time < CONCURRENT_TOTAL_THRESHOLD, (
            f"Concurrent issue took {total_time*1000:.1f}ms, exceeds "
            f"{CONCURRENT_TOTAL_THRESHOLD*1000:.0f}ms threshold"
        )


# -------------------------------------------------------------------------
# PRF-003: Validate ID response time
# -------------------------------------------------------------------------
class TestPRF003:
    """Validate a single ID 100 times and verify response time."""

    async def test_validate_id_response_time(
        self, client, perf_id_type, issue_id, validate_id
    ):
        # First get a valid ID to validate
        resp = await issue_id(client, perf_id_type)
        assert resp.status_code == 200
        test_id = resp.json()["response"]["id"]

        durations = []

        for _ in range(100):
            start = time.perf_counter()
            resp = await validate_id(client, perf_id_type, test_id)
            elapsed = time.perf_counter() - start

            assert resp.status_code == 200
            durations.append(elapsed)

        durations.sort()
        p50 = _percentile(durations, 50)
        p95 = _percentile(durations, 95)

        print(f"\n  Validate ID latency (n=100):")
        print(f"    p50={p50*1000:.1f}ms  p95={p95*1000:.1f}ms")
        print(f"    min={min(durations)*1000:.1f}ms  "
              f"max={max(durations)*1000:.1f}ms")

        assert p50 < VALIDATE_P50_THRESHOLD, (
            f"p50 latency {p50*1000:.1f}ms exceeds "
            f"{VALIDATE_P50_THRESHOLD*1000:.0f}ms threshold"
        )
        assert p95 < VALIDATE_P95_THRESHOLD, (
            f"p95 latency {p95*1000:.1f}ms exceeds "
            f"{VALIDATE_P95_THRESHOLD*1000:.0f}ms threshold"
        )


# -------------------------------------------------------------------------
# PRF-004: Health endpoint response time
# -------------------------------------------------------------------------
class TestPRF004:
    """Call health endpoint 50 times and verify response time."""

    async def test_health_endpoint_response_time(
        self, client, health_check
    ):
        durations = []

        for _ in range(50):
            start = time.perf_counter()
            resp = await health_check(client)
            elapsed = time.perf_counter() - start

            assert resp.status_code == 200
            durations.append(elapsed)

        durations.sort()
        p95 = _percentile(durations, 95)

        print(f"\n  Health latency (n=50): p95={p95*1000:.1f}ms")

        assert p95 < HEALTH_P95_THRESHOLD, (
            f"p95 latency {p95*1000:.1f}ms exceeds "
            f"{HEALTH_P95_THRESHOLD*1000:.0f}ms threshold"
        )
