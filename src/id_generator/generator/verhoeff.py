"""
Verhoeff checksum algorithm.

Used to generate and validate the checksum digit appended to every ID.
"""

# Dihedral group D5 multiplication table
_d = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

# Permutation table
_p = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

# Multiplicative inverse
_inv = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_checksum(number_str: str) -> str:
    """Compute the Verhoeff checksum digit for a numeric string.

    Args:
        number_str: A string of digits (without the checksum digit).

    Returns:
        A single character representing the checksum digit.
    """
    c = 0
    digits = [0] + [int(ch) for ch in reversed(number_str)]
    for i, digit in enumerate(digits):
        c = _d[c][_p[i % 8][digit]]
    return str(_inv[c])


def verhoeff_validate(number_str: str) -> bool:
    """Validate a numeric string that includes the Verhoeff checksum
    as the last digit.

    Args:
        number_str: A string of digits with the checksum as the last digit.

    Returns:
        True if the checksum is valid, False otherwise.
    """
    c = 0
    digits = [int(ch) for ch in reversed(number_str)]
    for i, digit in enumerate(digits):
        c = _d[c][_p[i % 8][digit]]
    return c == 0
