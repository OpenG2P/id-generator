"""
ID generation filter implementations.

All 10 filters from the functional specification. Each function returns
True if the ID PASSES the filter, False if it FAILS (should be rejected).
"""

from .verhoeff import verhoeff_validate

# Cyclic numbers (hardcoded per functional spec)
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


def filter_length(id_str: str, expected_length: int) -> bool:
    """Filter 1: ID must be exactly the configured length."""
    return len(id_str) == expected_length


def filter_not_start_with(id_str: str, not_start_with_list: list[str]) -> bool:
    """Filter 2: ID must not begin with specified digits."""
    if not id_str:
        return False
    return id_str[0] not in not_start_with_list


def filter_sequence(id_str: str, limit: int) -> bool:
    """Filter 3: No ascending/descending consecutive sequences >= limit."""
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
    """Filter 4: No same digit repeating within N positions."""
    for i in range(len(id_str)):
        for j in range(1, limit):
            if i + j < len(id_str) and id_str[i] == id_str[i + j]:
                return False
    return True


def filter_repeating_block(id_str: str, limit: int) -> bool:
    """Filter 5: No repeated digit blocks of length `limit`."""
    for i in range(len(id_str) - limit):
        block = id_str[i : i + limit]
        remaining = id_str[i + limit :]
        if block in remaining:
            return False
    return True


def filter_conjugative_even_digits(id_str: str, limit: int) -> bool:
    """Filter 6: No N or more consecutive even digits."""
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
    """Filter 7: First N digits must not equal last N digits."""
    if len(id_str) < 2 * limit:
        return True
    return id_str[:limit] != id_str[-limit:]


def filter_first_equals_reverse_last(id_str: str, limit: int) -> bool:
    """Filter 8: First N digits must not equal reverse of last N digits."""
    if len(id_str) < 2 * limit:
        return True
    return id_str[:limit] != id_str[-limit:][::-1]


def filter_restricted_numbers(id_str: str, restricted_list: list[str]) -> bool:
    """Filter 9: ID must not contain any blacklisted substrings."""
    for restricted in restricted_list:
        if restricted and restricted in id_str:
            return False
    return True


def filter_cyclic_numbers(id_str: str) -> bool:
    """Filter 10: ID must not contain any known cyclic number patterns."""
    for pattern in CYCLIC_NUMBERS:
        if pattern in id_str:
            return False
    return True


def check_all_filters(
    id_str: str,
    id_length: int,
    config: dict,
) -> bool:
    """Run Verhoeff validation and all 10 filters.

    Args:
        id_str: The ID to validate.
        id_length: Expected length for this ID type.
        config: Dict with filter configuration keys.

    Returns:
        True only if checksum is valid and all filters pass.
    """
    # Must be all digits
    if not id_str or not id_str.isdigit():
        return False

    if not verhoeff_validate(id_str):
        return False
    if not filter_length(id_str, id_length):
        return False
    if not filter_not_start_with(id_str, config["not_start_with"]):
        return False
    if not filter_sequence(id_str, config["sequence_limit"]):
        return False
    if not filter_repeating_digit(id_str, config["repeating_limit"]):
        return False
    if not filter_repeating_block(id_str, config["repeating_block_limit"]):
        return False
    if not filter_conjugative_even_digits(
        id_str, config["conjugative_even_digits_limit"]
    ):
        return False
    if not filter_first_equals_last(id_str, config["digits_group_limit"]):
        return False
    if not filter_first_equals_reverse_last(
        id_str, config["reverse_digits_group_limit"]
    ):
        return False
    if not filter_restricted_numbers(id_str, config["restricted_numbers"]):
        return False
    if not filter_cyclic_numbers(id_str):
        return False

    return True
