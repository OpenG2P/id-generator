"""
Core ID generation engine.

Generates random numeric IDs with Verhoeff checksum, filtered through
all 10 validation rules.
"""

import secrets

from .verhoeff import verhoeff_checksum
from .filters import (
    filter_length,
    filter_not_start_with,
    filter_sequence,
    filter_repeating_digit,
    filter_repeating_block,
    filter_conjugative_even_digits,
    filter_first_equals_last,
    filter_first_equals_reverse_last,
    filter_restricted_numbers,
    filter_cyclic_numbers,
)


def generate_candidate(id_length: int) -> str:
    """Generate a single random candidate ID with Verhoeff checksum.

    Args:
        id_length: Total ID length (including checksum digit).

    Returns:
        A candidate ID string (may or may not pass filters).
    """
    base_length = id_length - 1
    upper_bound = 10**base_length
    raw = secrets.randbelow(upper_bound)
    base_str = str(raw).zfill(base_length)
    return base_str + verhoeff_checksum(base_str)


def passes_all_filters(candidate: str, id_length: int, config: dict) -> bool:
    """Check if a candidate ID passes all 10 filters.

    Filters are ordered cheapest-first for early rejection.

    Args:
        candidate: The candidate ID string.
        id_length: Expected length for this namespace.
        config: Filter configuration dict.

    Returns:
        True if all filters pass.
    """
    # Cheapest filters first
    if not filter_not_start_with(candidate, config["not_start_with"]):
        return False
    if not filter_length(candidate, id_length):
        return False
    if not filter_sequence(candidate, config["sequence_limit"]):
        return False
    if not filter_repeating_digit(candidate, config["repeating_limit"]):
        return False
    if not filter_repeating_block(candidate, config["repeating_block_limit"]):
        return False
    if not filter_conjugative_even_digits(
        candidate, config["conjugative_even_digits_limit"]
    ):
        return False
    if not filter_first_equals_last(candidate, config["digits_group_limit"]):
        return False
    if not filter_first_equals_reverse_last(
        candidate, config["reverse_digits_group_limit"]
    ):
        return False
    if not filter_restricted_numbers(candidate, config["restricted_numbers"]):
        return False
    if not filter_cyclic_numbers(candidate):
        return False

    return True


def generate_batch(
    count: int,
    id_length: int,
    config: dict,
    max_attempts: int = 0,
) -> tuple[list[str], bool]:
    """Generate a batch of valid, unique IDs.

    Args:
        count: Target number of IDs to generate.
        id_length: Total ID length (including checksum).
        config: Filter configuration dict.
        max_attempts: Maximum consecutive failures before declaring
            exhaustion. 0 means no limit (keep trying).

    Returns:
        Tuple of (list of valid IDs, exhausted flag).
        If exhausted is True, the list may be shorter than count.
    """
    results = []
    seen = set()
    consecutive_failures = 0

    while len(results) < count:
        candidate = generate_candidate(id_length)

        if candidate in seen:
            consecutive_failures += 1
            if max_attempts > 0 and consecutive_failures >= max_attempts:
                return results, True
            continue

        if not passes_all_filters(candidate, id_length, config):
            consecutive_failures += 1
            if max_attempts > 0 and consecutive_failures >= max_attempts:
                return results, True
            continue

        # Valid and unique within this batch
        seen.add(candidate)
        results.append(candidate)
        consecutive_failures = 0

    return results, False
