"""Helpers for spreadsheet-style column position keys (A, B, ..., AA)."""

from __future__ import annotations

import re
from collections.abc import Sequence

_POSITION_KEY_PATTERN = re.compile(r"^[A-Z]+$")


def normalize_position_key(position_key: str) -> str:
    """Normalize and validate one position key."""
    normalized = position_key.strip().upper()
    if not _POSITION_KEY_PATTERN.fullmatch(normalized):
        raise ValueError(f"INVALID_COLUMN_POSITION_KEY:{position_key}")
    return normalized


def position_key_to_index(position_key: str) -> int:
    """Convert spreadsheet position key to zero-based index."""
    normalized = normalize_position_key(position_key)
    value = 0
    for char in normalized:
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value - 1


def index_to_position_key(index: int) -> str:
    """Convert zero-based index to spreadsheet position key."""
    if index < 0:
        raise ValueError(f"INVALID_COLUMN_INDEX:{index}")
    value = index + 1
    chars: list[str] = []
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        chars.append(chr(ord("A") + remainder))
    return "".join(reversed(chars))


def build_position_to_name(columns: Sequence[str]) -> dict[str, str]:
    """Build ordered position-key mapping for a column sequence."""
    return {index_to_position_key(index): name for index, name in enumerate(columns)}
