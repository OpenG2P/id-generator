"""
Category 3: Space Exhaustion Tests (EXS-001 through EXS-004)

Verify correct behavior when the ID space is fully consumed.
These tests MUST run after the exhaustive tests (Phase 3) have
drained test_ns_1 and test_ns_2.
"""

import pytest

pytestmark = [
    pytest.mark.exhaustion,
    pytest.mark.order(4),
    pytest.mark.asyncio(loop_scope="session"),
]


# -------------------------------------------------------------------------
# EXS-001: Exhaustion returns error
# -------------------------------------------------------------------------
class TestEXS001:
    """After all IDs are consumed, POST returns HTTP 410 with IDG-002."""

    async def test_exhaustion_returns_error(
        self, client, id_type_1, ns1_exhausted, issue_id
    ):
        assert ns1_exhausted["exhausted"], (
            "Precondition failed: EXH-001 must exhaust ID type first"
        )

        resp = await issue_id(client, id_type_1)

        assert resp.status_code == 410, (
            f"Expected HTTP 410 (Gone), got {resp.status_code}"
        )

        body = resp.json()
        assert len(body["errors"]) > 0
        assert body["errors"][0]["errorCode"] == "IDG-002"


# -------------------------------------------------------------------------
# EXS-002: Exhaustion error is permanent
# -------------------------------------------------------------------------
class TestEXS002:
    """Exhaustion error persists on subsequent requests (not transient)."""

    async def test_exhaustion_error_is_permanent(
        self, client, id_type_1, ns1_exhausted, issue_id
    ):
        assert ns1_exhausted["exhausted"]

        # Call twice to verify it's still exhausted
        for _ in range(2):
            resp = await issue_id(client, id_type_1)
            assert resp.status_code == 410
            assert resp.json()["errors"][0]["errorCode"] == "IDG-002"


# -------------------------------------------------------------------------
# EXS-003: Other ID type is unaffected
# -------------------------------------------------------------------------
class TestEXS003:
    """Exhaustion in one ID type does not affect other ID types.
    Uses the perf ID type which has a large pool."""

    async def test_other_id_type_unaffected(
        self, client, perf_id_type, ns1_exhausted, issue_id
    ):
        assert ns1_exhausted["exhausted"], (
            "Precondition: test_ns_1 must be exhausted"
        )

        # The perf ID type should still have IDs available
        resp = await issue_id(client, perf_id_type)

        assert resp.status_code == 200, (
            f"Expected HTTP 200 from unaffected ID type, "
            f"got {resp.status_code}"
        )

        body = resp.json()
        assert body["response"] is not None
        assert body["response"]["id"].isdigit()


# -------------------------------------------------------------------------
# EXS-004: Exhaustion response format
# -------------------------------------------------------------------------
class TestEXS004:
    """Exhaustion error response matches the standard MOSIP envelope."""

    async def test_exhaustion_response_format(
        self, client, id_type_1, ns1_exhausted, issue_id
    ):
        assert ns1_exhausted["exhausted"]

        resp = await issue_id(client, id_type_1)

        assert resp.status_code == 410
        assert "application/json" in resp.headers.get("content-type", "")

        body = resp.json()

        # Standard envelope fields present
        assert "id" in body
        assert "version" in body
        assert "responsetime" in body
        assert "response" in body
        assert "errors" in body

        # response is null on error
        assert body["response"] is None

        # errors array has the expected structure
        assert isinstance(body["errors"], list)
        assert len(body["errors"]) >= 1

        error = body["errors"][0]
        assert "errorCode" in error
        assert "message" in error
        assert error["errorCode"] == "IDG-002"
        assert len(error["message"]) > 0
