"""
Independent filter implementations for test cross-checking.

These are a second implementation of the 10 ID generation filters,
independent of the service code, used to:
  - Construct known-valid IDs for positive test cases.
  - Construct known-invalid IDs for negative test cases.
  - Cross-validate that the service's Validate API agrees.
"""

import secrets

from .verhoeff import build_valid_id, verhoeff_validate

# Cyclic numbers (hardcoded, same as functional spec)
CYCLIC_NUMBERS = [
    "142857",
    "0588235294117647",
    "052631578947368421",
    "0434782608695652173913",
    "0344827586206896551724137931",
    "0212765957446808510638297872340425531914893617",
    "0169491525423728813559322033898305084745762711864406779661",
    "016393442622950819672131147540983606557377049180327868852459",
    "010309278350515463917525773195876288659793814432989690721649"
    "484536082474226804123711340206185567",
]

# Default filter configuration (matching technical architecture defaults)
DEFAULT_CONFIG = {
    "sequence_limit": 3,
    "repeating_limit": 2,
    "repeating_block_limit": 2,
    "conjugative_even_digits_limit": 3,
    "digits_group_limit": 5,
    "reverse_digits_group_limit": 5,
    "not_start_with": ["0", "1"],
    "restricted_numbers": [],
}


# ---------------------------------------------------------------------------
# Individual filter functions
# Each returns True if the ID PASSES the filter, False if it FAILS.
# ---------------------------------------------------------------------------


def filter_length(id_str: str, expected_length: int) -> bool:
    """Filter 1: ID must be exactly the configured length."""
    return len(id_str) == expected_length


def filter_not_start_with(id_str: str, not_start_with_list: list[str]) -> bool:
    """Filter 2: ID must not begin with specified digits."""
    if not id_str:
        return False
    return id_str[0] not in not_start_with_list


def filter_sequence(id_str: str, limit: int) -> bool:
    """
    Filter 3: No ascending/descending consecutive digit sequences
    of length >= limit.

    Example: limit=3 means "123" (3 consecutive ascending) is rejected,
    but "12" is allowed.
    """
    if len(id_str) < 2:
        return True

    asc_run = 1
    desc_run = 1

    for i in range(1, len(id_str)):
        curr = int(id_str[i])
        prev = int(id_str[i - 1])

        if curr == prev + 1:
            asc_run += 1
        else:
            asc_run = 1

        if curr == prev - 1:
            desc_run += 1
        else:
            desc_run = 1

        if asc_run >= limit or desc_run >= limit:
            return False

    return True


def filter_repeating_digit(id_str: str, limit: int) -> bool:
    """
    Filter 4: No same digit repeating within N positions.

    With limit=2: "11" (distance 1) and "1x1" (distance 2) are rejected.
    "1xx1" (distance 3) is allowed.
    """
    for i in range(len(id_str)):
        for j in range(1, limit):
            if i + j < len(id_str) and id_str[i] == id_str[i + j]:
                return False
    return True


def filter_repeating_block(id_str: str, limit: int) -> bool:
    """
    Filter 5: No repeated digit blocks of length `limit`.

    With limit=2: any 2-digit block that appears again at a later
    non-overlapping position causes rejection.
    """
    for i in range(len(id_str) - limit):
        block = id_str[i : i + limit]
        # Search for the same block starting from position i+limit onwards
        remaining = id_str[i + limit :]
        if block in remaining:
            return False
    return True


def filter_conjugative_even_digits(id_str: str, limit: int) -> bool:
    """
    Filter 6: No N or more consecutive even digits (0, 2, 4, 6, 8).
    """
    even_run = 0
    for ch in id_str:
        if int(ch) % 2 == 0:
            even_run += 1
            if even_run >= limit:
                return False
        else:
            even_run = 0
    return True


def filter_first_equals_last(id_str: str, limit: int) -> bool:
    """
    Filter 7: First N digits must not equal last N digits.
    """
    if len(id_str) < 2 * limit:
        return True
    return id_str[:limit] != id_str[-limit:]


def filter_first_equals_reverse_last(id_str: str, limit: int) -> bool:
    """
    Filter 8: First N digits must not equal the reverse of last N digits.
    """
    if len(id_str) < 2 * limit:
        return True
    return id_str[:limit] != id_str[-limit:][::-1]


def filter_restricted_numbers(id_str: str, restricted_list: list[str]) -> bool:
    """
    Filter 9: ID must not contain any blacklisted substrings.
    """
    for restricted in restricted_list:
        if restricted and restricted in id_str:
            return False
    return True


def filter_cyclic_numbers(id_str: str) -> bool:
    """
    Filter 10: ID must not contain any of the 9 known cyclic number patterns.
    """
    for pattern in CYCLIC_NUMBERS:
        if pattern in id_str:
            return False
    return True


# ---------------------------------------------------------------------------
# Aggregate check
# ---------------------------------------------------------------------------


def check_all_filters(
    id_str: str,
    id_length: int,
    config: dict | None = None,
) -> bool:
    """
    Run all 10 filters on an ID. Returns True only if ALL filters pass.

    Also validates the Verhoeff checksum.
    """
    cfg = config or DEFAULT_CONFIG

    if not verhoeff_validate(id_str):
        return False
    if not filter_length(id_str, id_length):
        return False
    if not filter_not_start_with(id_str, cfg["not_start_with"]):
        return False
    if not filter_sequence(id_str, cfg["sequence_limit"]):
        return False
    if not filter_repeating_digit(id_str, cfg["repeating_limit"]):
        return False
    if not filter_repeating_block(id_str, cfg["repeating_block_limit"]):
        return False
    if not filter_conjugative_even_digits(
        id_str, cfg["conjugative_even_digits_limit"]
    ):
        return False
    if not filter_first_equals_last(id_str, cfg["digits_group_limit"]):
        return False
    if not filter_first_equals_reverse_last(
        id_str, cfg["reverse_digits_group_limit"]
    ):
        return False
    if not filter_restricted_numbers(id_str, cfg["restricted_numbers"]):
        return False
    if not filter_cyclic_numbers(id_str):
        return False

    return True


# ---------------------------------------------------------------------------
# Test ID construction utilities
# ---------------------------------------------------------------------------


def construct_valid_id(
    length: int,
    config: dict | None = None,
    max_attempts: int = 10000,
) -> str:
    """
    Construct a valid ID by trying random candidates until one passes
    all filters.

    Args:
        length: The total ID length (including checksum digit).
        config: Filter configuration. Defaults to DEFAULT_CONFIG.
        max_attempts: Safety limit to prevent infinite loops.

    Returns:
        A valid ID string.

    Raises:
        RuntimeError: If no valid ID found within max_attempts.
    """
    cfg = config or DEFAULT_CONFIG
    base_length = length - 1  # Verhoeff checksum is 1 digit

    for _ in range(max_attempts):
        # Generate random base digits
        # First digit: avoid not_start_with digits
        allowed_first = [
            str(d)
            for d in range(10)
            if str(d) not in cfg["not_start_with"]
        ]
        first = secrets.choice(allowed_first)
        rest = "".join(
            str(secrets.randbelow(10)) for _ in range(base_length - 1)
        )
        base = first + rest
        candidate = build_valid_id(base)

        if check_all_filters(candidate, length, cfg):
            return candidate

    raise RuntimeError(
        f"Could not construct a valid ID of length {length} "
        f"within {max_attempts} attempts"
    )


def construct_id_failing_filter(
    filter_name: str,
    length: int,
    config: dict | None = None,
) -> str:
    """
    Construct an ID that specifically fails the named filter while having
    a valid Verhoeff checksum.

    The returned ID may also fail other filters incidentally; the purpose
    is to guarantee that the named filter rejects it.

    Args:
        filter_name: One of: "not_start_with", "sequence_asc",
            "sequence_desc", "repeating_digit", "repeating_block",
            "conjugative_even", "first_equals_last",
            "first_equals_reverse_last", "restricted", "cyclic",
            "wrong_checksum", "wrong_length".
        length: The target ID type's ID length.
        config: Filter configuration. Defaults to DEFAULT_CONFIG.

    Returns:
        An ID string that fails the specified filter.
    """
    cfg = config or DEFAULT_CONFIG
    base_length = length - 1

    if filter_name == "not_start_with_zero":
        # Start with 0
        rest = "".join(
            str(secrets.randbelow(10)) for _ in range(base_length - 1)
        )
        return build_valid_id("0" + rest)

    if filter_name == "not_start_with_one":
        # Start with 1
        rest = "".join(
            str(secrets.randbelow(10)) for _ in range(base_length - 1)
        )
        return build_valid_id("1" + rest)

    if filter_name == "sequence_asc":
        # Create ascending sequence of length >= sequence_limit
        limit = cfg["sequence_limit"]
        # Build ascending run: e.g., "2345" for limit=3
        start_digit = 2
        seq = "".join(str(start_digit + i) for i in range(limit))
        # Pad to base_length
        padding_len = base_length - len(seq)
        if padding_len > 0:
            padding = "5" * padding_len
            base = seq + padding
        else:
            base = seq[:base_length]
        return build_valid_id(base)

    if filter_name == "sequence_desc":
        # Create descending sequence
        limit = cfg["sequence_limit"]
        start_digit = 9
        seq = "".join(str(start_digit - i) for i in range(limit))
        padding_len = base_length - len(seq)
        if padding_len > 0:
            padding = "5" * padding_len
            base = seq + padding
        else:
            base = seq[:base_length]
        return build_valid_id(base)

    if filter_name == "repeating_digit":
        # Same digit within limit distance: e.g., "2255" for limit=2
        base = "2" * base_length  # All same digit
        return build_valid_id(base)

    if filter_name == "repeating_block":
        # Repeated block: e.g., "4848" for limit=2
        limit = cfg["repeating_block_limit"]
        block = "48"[:limit]
        repetitions = (base_length // limit) + 1
        base = (block * repetitions)[:base_length]
        # Ensure first digit is allowed
        if base[0] in cfg["not_start_with"]:
            base = "4" + base[1:]
        return build_valid_id(base)

    if filter_name == "conjugative_even":
        # N consecutive even digits
        limit = cfg["conjugative_even_digits_limit"]
        evens = "2468024680"
        seq = evens[:limit]
        padding_len = base_length - len(seq)
        if padding_len > 0:
            # Use odd digit as first to avoid not_start_with issues
            base = "3" + seq + "3" * (padding_len - 1)
            base = base[:base_length]
        else:
            base = seq[:base_length]
        # Ensure first digit is allowed
        if base[0] in cfg["not_start_with"]:
            base = "3" + base[1:]
        return build_valid_id(base)

    if filter_name == "first_equals_last":
        # First N digits == last N digits (requires length >= 2*limit + 1)
        limit = cfg["digits_group_limit"]
        if length < 2 * limit + 1:  # +1 for checksum
            raise ValueError(
                f"ID length {length} too short for first_equals_last "
                f"with limit {limit} (need >= {2 * limit + 1})"
            )
        # Build: [block][filler][block] + checksum
        block = "23456"[:limit]
        filler_len = base_length - 2 * limit
        filler = "9" * filler_len if filler_len > 0 else ""
        base = block + filler + block
        base = base[:base_length]
        return build_valid_id(base)

    if filter_name == "first_equals_reverse_last":
        # First N digits == reverse of last N digits
        limit = cfg["reverse_digits_group_limit"]
        if length < 2 * limit + 1:
            raise ValueError(
                f"ID length {length} too short for "
                f"first_equals_reverse_last with limit {limit} "
                f"(need >= {2 * limit + 1})"
            )
        block = "23456"[:limit]
        reverse_block = block[::-1]
        filler_len = base_length - 2 * limit
        filler = "9" * filler_len if filler_len > 0 else ""
        base = block + filler + reverse_block
        base = base[:base_length]
        return build_valid_id(base)

    if filter_name == "cyclic":
        # Contains cyclic number 142857 (shortest, 6 digits)
        # Requires length >= 7 (6 for cyclic + 1 for checksum minimum)
        if length < 7:
            raise ValueError(
                f"ID length {length} too short for cyclic number test"
            )
        cyclic = "142857"
        padding_len = base_length - len(cyclic)
        if padding_len > 0:
            # Prefix with valid start digit + filler
            prefix = "2" + "9" * (padding_len - 1)
            base = prefix + cyclic
        else:
            base = cyclic[:base_length]
        base = base[:base_length]
        return build_valid_id(base)

    if filter_name == "wrong_checksum":
        # Valid base digits but wrong checksum
        valid_id = construct_valid_id(length, cfg)
        last_digit = int(valid_id[-1])
        wrong_digit = (last_digit + 1) % 10
        return valid_id[:-1] + str(wrong_digit)

    if filter_name == "wrong_length_short":
        # ID that is too short
        return construct_valid_id(length - 1, cfg)

    if filter_name == "wrong_length_long":
        # ID that is too long
        return construct_valid_id(length + 1, cfg)

    raise ValueError(f"Unknown filter name: {filter_name}")
