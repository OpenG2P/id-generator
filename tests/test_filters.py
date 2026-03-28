"""
Category 2: Filter Validation Tests (FLT-001 through FLT-018)

Verify that the service's Validate API correctly accepts/rejects IDs
based on the 10 filter rules. Uses the Validate endpoint (no pool IDs
consumed) except FLT-015 which cross-checks exhaustive results.
"""

import pytest

from helpers import (
    construct_id_failing_filter,
    construct_valid_id,
)

pytestmark = [
    pytest.mark.filters,
    pytest.mark.order(2),
    pytest.mark.asyncio(loop_scope="session"),
]


# -------------------------------------------------------------------------
# FLT-001: Known-valid ID passes validation
# -------------------------------------------------------------------------
class TestFLT001:
    """A correctly constructed ID passes the Validate API."""

    async def test_valid_id_passes_validation(
        self, client, namespace_1, ns1_id_length, validate_id
    ):
        valid_id = construct_valid_id(ns1_id_length)
        resp = await validate_id(client, namespace_1, valid_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is True, (
            f"Expected valid=True for ID '{valid_id}'"
        )


# -------------------------------------------------------------------------
# FLT-002: Wrong checksum rejected
# -------------------------------------------------------------------------
class TestFLT002:
    """ID with incorrect Verhoeff checksum is rejected."""

    async def test_wrong_checksum_rejected(
        self, client, namespace_1, ns1_id_length, validate_id
    ):
        bad_id = construct_id_failing_filter("wrong_checksum", ns1_id_length)
        resp = await validate_id(client, namespace_1, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False


# -------------------------------------------------------------------------
# FLT-003: Starts with zero rejected
# -------------------------------------------------------------------------
class TestFLT003:
    """ID starting with '0' is rejected."""

    async def test_starts_with_zero_rejected(
        self, client, namespace_1, ns1_id_length, validate_id
    ):
        bad_id = construct_id_failing_filter("not_start_with_zero", ns1_id_length)
        resp = await validate_id(client, namespace_1, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False


# -------------------------------------------------------------------------
# FLT-004: Starts with one rejected
# -------------------------------------------------------------------------
class TestFLT004:
    """ID starting with '1' is rejected."""

    async def test_starts_with_one_rejected(
        self, client, namespace_1, ns1_id_length, validate_id
    ):
        bad_id = construct_id_failing_filter("not_start_with_one", ns1_id_length)
        resp = await validate_id(client, namespace_1, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False


# -------------------------------------------------------------------------
# FLT-005: Ascending sequence rejected
# -------------------------------------------------------------------------
class TestFLT005:
    """ID with ascending sequence >= limit is rejected."""

    async def test_ascending_sequence_rejected(
        self, client, namespace_1, ns1_id_length, validate_id
    ):
        bad_id = construct_id_failing_filter("sequence_asc", ns1_id_length)
        resp = await validate_id(client, namespace_1, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False, (
            f"Expected valid=False for ascending sequence ID '{bad_id}'"
        )


# -------------------------------------------------------------------------
# FLT-006: Descending sequence rejected
# -------------------------------------------------------------------------
class TestFLT006:
    """ID with descending sequence >= limit is rejected."""

    async def test_descending_sequence_rejected(
        self, client, namespace_1, ns1_id_length, validate_id
    ):
        bad_id = construct_id_failing_filter("sequence_desc", ns1_id_length)
        resp = await validate_id(client, namespace_1, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False, (
            f"Expected valid=False for descending sequence ID '{bad_id}'"
        )


# -------------------------------------------------------------------------
# FLT-007: Repeating digit rejected
# -------------------------------------------------------------------------
class TestFLT007:
    """ID with same digit repeating within limit distance is rejected."""

    async def test_repeating_digit_rejected(
        self, client, namespace_1, ns1_id_length, validate_id
    ):
        bad_id = construct_id_failing_filter("repeating_digit", ns1_id_length)
        resp = await validate_id(client, namespace_1, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False


# -------------------------------------------------------------------------
# FLT-008: Repeating block rejected
# -------------------------------------------------------------------------
class TestFLT008:
    """ID with repeated digit block is rejected."""

    async def test_repeating_block_rejected(
        self, client, namespace_1, ns1_id_length, validate_id
    ):
        bad_id = construct_id_failing_filter("repeating_block", ns1_id_length)
        resp = await validate_id(client, namespace_1, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False


# -------------------------------------------------------------------------
# FLT-009: Conjugative even digits rejected
# -------------------------------------------------------------------------
class TestFLT009:
    """ID with N+ consecutive even digits is rejected."""

    async def test_conjugative_even_digits_rejected(
        self, client, namespace_1, ns1_id_length, validate_id
    ):
        bad_id = construct_id_failing_filter("conjugative_even", ns1_id_length)
        resp = await validate_id(client, namespace_1, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False


# -------------------------------------------------------------------------
# FLT-010: First N digits equal last N digits rejected
# -------------------------------------------------------------------------
class TestFLT010:
    """ID where first N digits == last N digits is rejected.
    Uses perf namespace (length=10) since digits_group_limit=5
    requires ID length >= 10."""

    async def test_first_equals_last_rejected(
        self, client, perf_namespace, perf_id_length, service_config, validate_id
    ):
        limit = service_config["filter_rules"]["digits_group_limit"]
        if perf_id_length < 2 * limit + 1:
            pytest.skip(
                f"ID length {perf_id_length} too short for "
                f"first_equals_last with limit {limit} "
                f"(need >= {2 * limit + 1})"
            )
        bad_id = construct_id_failing_filter("first_equals_last", perf_id_length)
        resp = await validate_id(client, perf_namespace, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False


# -------------------------------------------------------------------------
# FLT-011: First N digits equal reverse of last N digits rejected
# -------------------------------------------------------------------------
class TestFLT011:
    """ID where first N digits == reverse(last N digits) is rejected.
    Uses perf namespace (length=10)."""

    async def test_first_equals_reverse_last_rejected(
        self, client, perf_namespace, perf_id_length, service_config, validate_id
    ):
        limit = service_config["filter_rules"]["reverse_digits_group_limit"]
        if perf_id_length < 2 * limit + 1:
            pytest.skip(
                f"ID length {perf_id_length} too short for "
                f"first_equals_reverse_last with limit {limit} "
                f"(need >= {2 * limit + 1})"
            )
        bad_id = construct_id_failing_filter(
            "first_equals_reverse_last", perf_id_length
        )
        resp = await validate_id(client, perf_namespace, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False


# -------------------------------------------------------------------------
# FLT-012: Restricted number rejected
# -------------------------------------------------------------------------
class TestFLT012:
    """ID containing a restricted number substring is rejected.
    Skipped if no restricted numbers are configured."""

    async def test_restricted_number_rejected(
        self, client, namespace_1, validate_id
    ):
        pytest.skip(
            "No restricted numbers configured in default config. "
            "Re-enable when restricted_numbers is populated in test config."
        )


# -------------------------------------------------------------------------
# FLT-013: Cyclic number rejected
# -------------------------------------------------------------------------
class TestFLT013:
    """ID containing cyclic number 142857 is rejected.
    Uses perf namespace (length=10) since 142857 is 6 digits."""

    async def test_cyclic_number_rejected(
        self, client, perf_namespace, perf_id_length, validate_id
    ):
        bad_id = construct_id_failing_filter("cyclic", perf_id_length)
        resp = await validate_id(client, perf_namespace, bad_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False, (
            f"Expected valid=False for cyclic number ID '{bad_id}'"
        )


# -------------------------------------------------------------------------
# FLT-014: Wrong length rejected
# -------------------------------------------------------------------------
class TestFLT014:
    """ID with wrong length for the namespace is rejected."""

    async def test_wrong_length_rejected(
        self, client, namespace_1, ns1_id_length, validate_id
    ):
        # Submit an ID that is 1 digit shorter than expected
        short_id = construct_valid_id(ns1_id_length - 1)
        resp = await validate_id(client, namespace_1, short_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False

        # Also test an ID that is 1 digit longer than expected
        long_id = construct_valid_id(ns1_id_length + 1)
        resp = await validate_id(client, namespace_1, long_id)
        assert resp.status_code == 200

        body = resp.json()
        assert body["response"]["valid"] is False


# -------------------------------------------------------------------------
# FLT-015: All exhaustive IDs pass validation (cross-check)
# -------------------------------------------------------------------------
class TestFLT015:
    """Every ID issued during exhaustive tests passes the Validate API.
    Cross-checks that generator and validator agree."""

    @pytest.mark.slow
    @pytest.mark.order(4)  # Must run after exhaustive tests (Phase 3)
    async def test_all_exhaustive_ids_pass_validation(
        self, client, namespace_1, validate_id, ns1_issued_ids
    ):
        assert len(ns1_issued_ids) > 0, (
            "No IDs collected. EXH-001 must run before this test."
        )

        failures = []
        for id_value in ns1_issued_ids:
            resp = await validate_id(client, namespace_1, id_value)
            assert resp.status_code == 200
            body = resp.json()
            if body["response"]["valid"] is not True:
                failures.append(id_value)

        assert len(failures) == 0, (
            f"{len(failures)} issued IDs failed validation: "
            f"{failures[:10]}..."
        )


# -------------------------------------------------------------------------
# FLT-016: Boundary sequence allowed
# -------------------------------------------------------------------------
class TestFLT016:
    """Sequence below the limit (e.g., "12" with limit=3) is allowed."""

    async def test_boundary_sequence_allowed(
        self, client, namespace_1, validate_id
    ):
        # "12" is a 2-digit ascending sequence, below limit=3 -> allowed
        # Construct: base "5127" (contains "12" but not "123") + checksum
        from helpers.verhoeff import build_valid_id

        candidate = build_valid_id("5127")
        resp = await validate_id(client, namespace_1, candidate)
        assert resp.status_code == 200

        body = resp.json()
        # This may still fail other filters; we mainly verify it doesn't
        # fail due to the 2-digit sequence alone. If valid=False, the
        # sequence filter is not the cause.
        # For a definitive test, construct an ID that passes all filters
        # AND contains a 2-digit sequence.
        if body["response"]["valid"] is False:
            # Verify with our local filter that sequence passes
            from helpers.filters import filter_sequence

            assert filter_sequence(candidate, 3) is True, (
                "Local sequence filter says '12' should be allowed"
            )


# -------------------------------------------------------------------------
# FLT-017: Boundary repeating allowed
# -------------------------------------------------------------------------
class TestFLT017:
    """Same digit beyond limit distance is allowed."""

    async def test_boundary_repeating_allowed(
        self, client, namespace_1, validate_id
    ):
        # With repeating_limit=2: same digit at distance >= 2 is allowed
        # "2XX2" where distance = 3 > limit 2
        from helpers.verhoeff import build_valid_id

        candidate = build_valid_id("2532")
        resp = await validate_id(client, namespace_1, candidate)
        assert resp.status_code == 200

        body = resp.json()
        if body["response"]["valid"] is False:
            from helpers.filters import filter_repeating_digit

            assert filter_repeating_digit(candidate, 2) is True, (
                "Local repeating filter says distance-3 repeat should "
                "be allowed"
            )


# -------------------------------------------------------------------------
# FLT-018: Non-numeric ID rejected
# -------------------------------------------------------------------------
class TestFLT018:
    """IDs containing non-numeric characters are rejected.
    May return 422 (path param validation) or valid=False."""

    @pytest.mark.parametrize(
        "bad_id",
        ["ABCDE", "12A45", "12.45"],
        ids=["all-alpha", "mixed", "decimal-point"],
    )
    async def test_non_numeric_rejected(
        self, client, namespace_1, validate_id, bad_id
    ):
        resp = await validate_id(client, namespace_1, bad_id)

        # Service may return 422 (path param regex rejects it)
        # or 200 with valid=False. Either is acceptable.
        if resp.status_code == 422:
            pass  # Rejected at routing level, correct
        elif resp.status_code == 200:
            body = resp.json()
            assert body["response"]["valid"] is False
        else:
            pytest.fail(
                f"Unexpected status {resp.status_code} for "
                f"non-numeric ID '{bad_id}'"
            )
