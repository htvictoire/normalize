"""Boolean value detection for column type inference."""

from __future__ import annotations

from shared.parsing.boolean import BOOLEAN_FALSE_TOKENS, BOOLEAN_TRUE_TOKENS


def is_boolean(value: str) -> bool:
    """Return True if the value matches a known boolean token."""
    normalized = value.strip().lower()
    return normalized in BOOLEAN_TRUE_TOKENS or normalized in BOOLEAN_FALSE_TOKENS
