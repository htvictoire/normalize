"""Shared helpers for source format inference."""

from __future__ import annotations


def looks_numeric(value: str) -> bool:
    """Return True when digits make up at least half the characters of value."""
    stripped = value.strip()
    if not stripped:
        return False
    digits = sum(1 for char in stripped if char.isdigit())
    return digits > 0 and digits >= max(len(stripped) // 2, 1)
