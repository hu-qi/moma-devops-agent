from typing import Tuple
import re


def parse_date(date_str: str) -> Tuple[int, int, int]:
    """Parse a date string in YYYY-MM-DD format and return (year, month, day).

    Raises ValueError for invalid formats.

    Example
    -------
    >>> parse_date("2024-03-15")
    (2024, 3, 15)
    """
    # BUG: pattern requires single-digit month/day — rejects zero-padded values
    m = re.fullmatch(r"(\d{4})-([1-9]|1[0-2])-([1-9]|[12]\d|3[01])", date_str)
    if m is None:
        raise ValueError(f"Invalid date format: {date_str!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))
