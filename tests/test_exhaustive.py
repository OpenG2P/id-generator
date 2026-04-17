"""
Category 1: Exhaustive Uniqueness & Randomness Tests (EXH-001 through EXH-008)

These tests issue EVERY possible ID from small-space ID types (length=5)
and verify uniqueness, randomness, distribution, and ID type independence.

WARNING: Running these tests permanently consumes all IDs in id_type_1
and id_type_2 (typically farmer and household). The ID types must
be reset (truncate tables) before re-running.
"""

import asyncio
import math
import statistics

import pytest

pytestmark = [
    pytest.mark.exhaustive,
    pytest.mark.order(3),
    pytest.mark.asyncio(loop_scope="session"),
]

# Safety limit to prevent infinite loops
MAX_ISSUE_ATTEMPTS = 100_000


# -------------------------------------------------------------------------
# Helper: drain an ID type (issue all IDs until exhausted)
# -------------------------------------------------------------------------
async def _drain_id_type(client, id_type, id_list, exhausted_flag):
    """Issue all IDs from an ID type until the space is exhausted.

    Appends each issued ID to id_list. Sets exhausted_flag["exhausted"]
    to True when HTTP 410 (IDG-002) is received.
    """
    for _ in range(MAX_ISSUE_ATTEMPTS):
        resp = await client.post(f"/v1/idgenerator/{id_type}/id")

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
        elif resp.status_code == 500:
            # Transient server error (e.g., deadlock). Retry after
            # a brief pause.
            await asyncio.sleep(0.1)
            continue
        else:
            pytest.fail(
                f"Unexpected status {resp.status_code} while draining "
                f"ID type '{id_type}': {resp.text}"
            )

    pytest.fail(
        f"Safety limit ({MAX_ISSUE_ATTEMPTS}) reached while draining "
        f"ID type '{id_type}'. Got {len(id_list)} IDs without "
        f"exhaustion."
    )


# -------------------------------------------------------------------------
# EXH-001: All IDs unique in ID type 1
# -------------------------------------------------------------------------
class TestEXH001:
    """Issue all IDs from id_type_1. Assert no duplicates."""

    @pytest.mark.slow
    @pytest.mark.order(3.0)
    async def test_all_ids_unique_ns1(
        self, client, id_type_1, id_type_1_issued_ids, id_type_1_exhausted
    ):
        await _drain_id_type(
            client, id_type_1, id_type_1_issued_ids, id_type_1_exhausted
        )

        assert id_type_1_exhausted["exhausted"], (
            "ID type was not exhausted within the safety limit"
        )
        assert len(id_type_1_issued_ids) > 0, "No IDs were issued"

        unique_count = len(set(id_type_1_issued_ids))
        total_count = len(id_type_1_issued_ids)

        assert unique_count == total_count, (
            f"Duplicate IDs found! {total_count} issued but only "
            f"{unique_count} unique. Duplicates: "
            f"{total_count - unique_count}"
        )


# -------------------------------------------------------------------------
# EXH-002: All IDs unique in ID type 2
# -------------------------------------------------------------------------
class TestEXH002:
    """Issue all IDs from id_type_2. Assert no duplicates."""

    @pytest.mark.slow
    @pytest.mark.order(3.0)
    async def test_all_ids_unique_ns2(
        self, client, id_type_2, id_type_2_issued_ids, id_type_2_exhausted
    ):
        await _drain_id_type(
            client, id_type_2, id_type_2_issued_ids, id_type_2_exhausted
        )

        assert id_type_2_exhausted["exhausted"]
        assert len(id_type_2_issued_ids) > 0

        unique_count = len(set(id_type_2_issued_ids))
        total_count = len(id_type_2_issued_ids)

        assert unique_count == total_count, (
            f"Duplicate IDs found! {total_count} issued but only "
            f"{unique_count} unique."
        )


# -------------------------------------------------------------------------
# EXH-003: IDs not in sequential order (ID type 1)
# -------------------------------------------------------------------------
class TestEXH003:
    """Issued IDs are not in ascending or descending numeric order."""

    @pytest.mark.order(3.1)
    async def test_ids_not_sequential_ns1(self, id_type_1_issued_ids):
        assert len(id_type_1_issued_ids) > 0, "EXH-001 must run first"

        int_ids = [int(x) for x in id_type_1_issued_ids]
        sorted_asc = sorted(int_ids)
        sorted_desc = sorted(int_ids, reverse=True)

        assert int_ids != sorted_asc, (
            "IDs were issued in ascending order — not random!"
        )
        assert int_ids != sorted_desc, (
            "IDs were issued in descending order — not random!"
        )


# -------------------------------------------------------------------------
# EXH-004: IDs not in sequential order (ID type 2)
# -------------------------------------------------------------------------
class TestEXH004:
    """Issued IDs from ID type 2 are not sequentially ordered."""

    @pytest.mark.order(3.1)
    async def test_ids_not_sequential_ns2(self, id_type_2_issued_ids):
        assert len(id_type_2_issued_ids) > 0, "EXH-002 must run first"

        int_ids = [int(x) for x in id_type_2_issued_ids]
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
    async def test_ids_not_clustered(self, id_type_1_issued_ids):
        assert len(id_type_1_issued_ids) > 10, "EXH-001 must run first"

        int_ids = [int(x) for x in id_type_1_issued_ids]
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

    This is a sanity check, not a strict uniformity test. The 10 filter
    rules (no repeating digits, no sequences, no consecutive even digits,
    etc.) create inherent bias in digit distribution — especially for
    short IDs where filters constrain a large fraction of the space.

    We verify that no single digit dominates a position (>50% of
    occurrences), which would indicate a generation bug.
    """

    @pytest.mark.order(3.1)
    async def test_digit_distribution(self, id_type_1_issued_ids):
        assert len(id_type_1_issued_ids) > 100, "EXH-001 must run first"

        total_ids = len(id_type_1_issued_ids)
        id_length = len(id_type_1_issued_ids[0])

        # Check digit distribution for middle positions
        # Position 0 is non-uniform (only 2-9 due to not_start_with)
        # Position id_length-1 is Verhoeff checksum (deterministic)
        for pos in range(1, id_length - 1):
            counts = [0] * 10
            for id_str in id_type_1_issued_ids:
                digit = int(id_str[pos])
                counts[digit] += 1

            # No single digit should account for >50% of all IDs at
            # any position. This catches gross bugs (e.g., always
            # generating "5" at position 2) while tolerating the
            # filter-induced skew that is inherent in short IDs.
            max_count = max(counts)
            max_digit = counts.index(max_count)
            max_pct = max_count / total_ids * 100

            assert max_pct < 50, (
                f"Position {pos}: digit '{max_digit}' appears "
                f"{max_pct:.1f}% of the time ({max_count}/{total_ids}). "
                f"Distribution: {counts}"
            )


# -------------------------------------------------------------------------
# EXH-007: ID type independence
# -------------------------------------------------------------------------
class TestEXH007:
    """The issuance order differs between ID type 1 and ID type 2."""

    @pytest.mark.order(3.1)
    async def test_id_type_independence(
        self, id_type_1_issued_ids, id_type_2_issued_ids
    ):
        assert len(id_type_1_issued_ids) > 0, "EXH-001 must run first"
        assert len(id_type_2_issued_ids) > 0, "EXH-002 must run first"

        # Compare the issuance ORDER (not just the set of IDs)
        min_len = min(len(id_type_1_issued_ids), len(id_type_2_issued_ids))
        prefix_1 = id_type_1_issued_ids[:min_len]
        prefix_2 = id_type_2_issued_ids[:min_len]

        assert prefix_1 != prefix_2, (
            "Both ID types issued IDs in the exact same order — "
            "they should be independently randomized"
        )


# -------------------------------------------------------------------------
# EXH-008: Total count within expected range
# -------------------------------------------------------------------------
class TestEXH008:
    """Total number of valid IDs falls within the mathematically
    expected range based on the ID type's id_length."""

    @pytest.mark.order(3.1)
    async def test_total_count_within_expected_range(
        self, id_type_1_issued_ids, id_type_1_length
    ):
        assert len(id_type_1_issued_ids) > 0, "EXH-001 must run first"

        total = len(id_type_1_issued_ids)

        # Raw space: first digit 2-9 (8 options) x remaining digits (10^N)
        # where N = id_length - 2 (one for checksum, one for first digit)
        raw_space = 8 * (10 ** (id_type_1_length - 2))

        # Filters reduce this significantly (typically 30-60% pass rate).
        # Use conservative bounds:
        #   Lower: ~5% of raw space (very aggressive filters)
        #   Upper: raw space itself (no IDs filtered, theoretical max)
        min_expected = max(100, int(raw_space * 0.05))
        max_expected = raw_space

        assert min_expected <= total <= max_expected, (
            f"Total IDs issued ({total}) outside expected range "
            f"[{min_expected}, {max_expected}] for id_length={id_type_1_length} "
            f"(raw_space={raw_space})"
        )
