"""
Category 1: Exhaustive Uniqueness & Randomness Tests (EXH-001 through EXH-008)

These tests issue EVERY possible ID from small-space namespaces (length=5)
and verify uniqueness, randomness, distribution, and namespace independence.

WARNING: Running these tests permanently consumes all IDs in test_ns_1
and test_ns_2. The namespaces must be reset before re-running.
"""

import math
import statistics

import pytest

pytestmark = [pytest.mark.exhaustive, pytest.mark.order(3)]

# Safety limit to prevent infinite loops
MAX_ISSUE_ATTEMPTS = 100_000


# -------------------------------------------------------------------------
# Helper: drain a namespace (issue all IDs until exhausted)
# -------------------------------------------------------------------------
async def _drain_namespace(client, namespace, id_list, exhausted_flag):
    """Issue all IDs from a namespace until the space is exhausted.

    Appends each issued ID to id_list. Sets exhausted_flag["exhausted"]
    to True when HTTP 410 (IDG-002) is received.
    """
    for _ in range(MAX_ISSUE_ATTEMPTS):
        resp = await client.post(f"/v1/idgenerator/{namespace}/id")

        if resp.status_code == 200:
            issued_id = resp.json()["response"]["id"]
            id_list.append(issued_id)
        elif resp.status_code == 410:
            # IDG-002: space exhausted
            exhausted_flag["exhausted"] = True
            return
        elif resp.status_code == 503:
            # IDG-001: temporary, pool replenishment in progress
            # Retry immediately (the service should replenish quickly)
            continue
        else:
            pytest.fail(
                f"Unexpected status {resp.status_code} while draining "
                f"namespace '{namespace}': {resp.text}"
            )

    pytest.fail(
        f"Safety limit ({MAX_ISSUE_ATTEMPTS}) reached while draining "
        f"namespace '{namespace}'. Got {len(id_list)} IDs without "
        f"exhaustion."
    )


# -------------------------------------------------------------------------
# EXH-001: All IDs unique in namespace 1
# -------------------------------------------------------------------------
class TestEXH001:
    """Issue all IDs from test_ns_1. Assert no duplicates."""

    @pytest.mark.slow
    @pytest.mark.order(3.0)
    async def test_all_ids_unique_ns1(
        self, client, namespace_1, ns1_issued_ids, ns1_exhausted
    ):
        await _drain_namespace(
            client, namespace_1, ns1_issued_ids, ns1_exhausted
        )

        assert ns1_exhausted["exhausted"], (
            "Namespace was not exhausted within the safety limit"
        )
        assert len(ns1_issued_ids) > 0, "No IDs were issued"

        unique_count = len(set(ns1_issued_ids))
        total_count = len(ns1_issued_ids)

        assert unique_count == total_count, (
            f"Duplicate IDs found! {total_count} issued but only "
            f"{unique_count} unique. Duplicates: "
            f"{total_count - unique_count}"
        )


# -------------------------------------------------------------------------
# EXH-002: All IDs unique in namespace 2
# -------------------------------------------------------------------------
class TestEXH002:
    """Issue all IDs from test_ns_2. Assert no duplicates."""

    @pytest.mark.slow
    @pytest.mark.order(3.0)
    async def test_all_ids_unique_ns2(
        self, client, namespace_2, ns2_issued_ids, ns2_exhausted
    ):
        await _drain_namespace(
            client, namespace_2, ns2_issued_ids, ns2_exhausted
        )

        assert ns2_exhausted["exhausted"]
        assert len(ns2_issued_ids) > 0

        unique_count = len(set(ns2_issued_ids))
        total_count = len(ns2_issued_ids)

        assert unique_count == total_count, (
            f"Duplicate IDs found! {total_count} issued but only "
            f"{unique_count} unique."
        )


# -------------------------------------------------------------------------
# EXH-003: IDs not in sequential order (namespace 1)
# -------------------------------------------------------------------------
class TestEXH003:
    """Issued IDs are not in ascending or descending numeric order."""

    @pytest.mark.order(3.1)
    async def test_ids_not_sequential_ns1(self, ns1_issued_ids):
        assert len(ns1_issued_ids) > 0, "EXH-001 must run first"

        int_ids = [int(x) for x in ns1_issued_ids]
        sorted_asc = sorted(int_ids)
        sorted_desc = sorted(int_ids, reverse=True)

        assert int_ids != sorted_asc, (
            "IDs were issued in ascending order — not random!"
        )
        assert int_ids != sorted_desc, (
            "IDs were issued in descending order — not random!"
        )


# -------------------------------------------------------------------------
# EXH-004: IDs not in sequential order (namespace 2)
# -------------------------------------------------------------------------
class TestEXH004:
    """Issued IDs from namespace 2 are not sequentially ordered."""

    @pytest.mark.order(3.1)
    async def test_ids_not_sequential_ns2(self, ns2_issued_ids):
        assert len(ns2_issued_ids) > 0, "EXH-002 must run first"

        int_ids = [int(x) for x in ns2_issued_ids]
        sorted_asc = sorted(int_ids)
        sorted_desc = sorted(int_ids, reverse=True)

        assert int_ids != sorted_asc
        assert int_ids != sorted_desc


# -------------------------------------------------------------------------
# EXH-005: IDs not clustered
# -------------------------------------------------------------------------
class TestEXH005:
    """Deltas between consecutive issued IDs are highly varied (not
    constant), indicating randomized issuance order."""

    @pytest.mark.order(3.1)
    async def test_ids_not_clustered(self, ns1_issued_ids):
        assert len(ns1_issued_ids) > 10, "EXH-001 must run first"

        int_ids = [int(x) for x in ns1_issued_ids]
        deltas = [
            abs(int_ids[i + 1] - int_ids[i])
            for i in range(len(int_ids) - 1)
        ]

        std_dev = statistics.stdev(deltas)

        # For truly random ordering, std dev of deltas should be large
        # relative to the ID space. A threshold of 100 is conservative
        # for a 5-digit ID space (~2000-5000 IDs).
        assert std_dev > 100, (
            f"Delta std dev is only {std_dev:.1f} — IDs may be clustered "
            f"or near-sequential"
        )


# -------------------------------------------------------------------------
# EXH-006: Digit distribution
# -------------------------------------------------------------------------
class TestEXH006:
    """Digit frequency distribution across all issued IDs is reasonable.
    Uses chi-squared goodness-of-fit test (manual implementation)."""

    @pytest.mark.order(3.1)
    async def test_digit_distribution(self, ns1_issued_ids):
        assert len(ns1_issued_ids) > 100, "EXH-001 must run first"

        total_ids = len(ns1_issued_ids)
        id_length = len(ns1_issued_ids[0])

        # Check digit distribution for middle positions (1, 2)
        # Position 0 is non-uniform (only 2-9 due to not_start_with)
        # Position id_length-1 is Verhoeff checksum (deterministic)
        for pos in range(1, id_length - 1):
            counts = [0] * 10
            for id_str in ns1_issued_ids:
                digit = int(id_str[pos])
                counts[digit] += 1

            # Expected: roughly uniform across 0-9
            expected = total_ids / 10.0

            # Chi-squared statistic
            chi2 = sum(
                (observed - expected) ** 2 / expected
                for observed in counts
            )

            # Degrees of freedom = 10 - 1 = 9
            # Chi-squared critical value at p=0.001 with df=9 is ~27.88
            # Using a very lenient threshold to avoid flaky tests
            assert chi2 < 50, (
                f"Position {pos}: chi-squared={chi2:.1f} exceeds threshold. "
                f"Distribution: {counts}"
            )


# -------------------------------------------------------------------------
# EXH-007: Namespace independence
# -------------------------------------------------------------------------
class TestEXH007:
    """The issuance order differs between namespace 1 and namespace 2."""

    @pytest.mark.order(3.1)
    async def test_namespace_independence(
        self, ns1_issued_ids, ns2_issued_ids
    ):
        assert len(ns1_issued_ids) > 0, "EXH-001 must run first"
        assert len(ns2_issued_ids) > 0, "EXH-002 must run first"

        # Compare the issuance ORDER (not just the set of IDs)
        min_len = min(len(ns1_issued_ids), len(ns2_issued_ids))
        ns1_prefix = ns1_issued_ids[:min_len]
        ns2_prefix = ns2_issued_ids[:min_len]

        assert ns1_prefix != ns2_prefix, (
            "Both namespaces issued IDs in the exact same order — "
            "they should be independently randomized"
        )


# -------------------------------------------------------------------------
# EXH-008: Total count within expected range
# -------------------------------------------------------------------------
class TestEXH008:
    """Total number of valid IDs falls within the mathematically
    expected range for 5-digit IDs with standard filters."""

    @pytest.mark.order(3.1)
    async def test_total_count_within_expected_range(self, ns1_issued_ids):
        assert len(ns1_issued_ids) > 0, "EXH-001 must run first"

        total = len(ns1_issued_ids)

        # For 5-digit IDs:
        #   Base space: first digit 2-9 (8 options) x 3 more digits (10^3)
        #   = 8000 base candidates, each gets a Verhoeff checksum
        #   Filters reduce this significantly
        # Conservative bounds:
        min_expected = 500
        max_expected = 8000

        assert min_expected <= total <= max_expected, (
            f"Total IDs issued ({total}) outside expected range "
            f"[{min_expected}, {max_expected}]"
        )
