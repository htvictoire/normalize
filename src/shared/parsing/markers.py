"""Sign marker constants and SQL expression helpers."""

from __future__ import annotations

import re

from shared.db.sql import quote_string

NEGATIVE_SIGN_MARKERS: frozenset[str] = frozenset({"CR", "-"})
POSITIVE_SIGN_MARKERS: frozenset[str] = frozenset({"DR", "+"})
KNOWN_SIGN_MARKERS: tuple[str, ...] = tuple(sorted(NEGATIVE_SIGN_MARKERS | POSITIVE_SIGN_MARKERS))


def negative_word_marker(cr_negative: bool) -> str:
    """Return the CR/DR token that reads as negative."""
    return "CR" if cr_negative else "DR"


def positive_word_marker(cr_negative: bool) -> str:
    """Return the CR/DR token that reads as positive."""
    return "DR" if cr_negative else "CR"


def negative_sign_markers(cr_negative: bool) -> tuple[str, str]:
    """Return the negative markers: the negative CR/DR token plus the minus sign."""
    return (negative_word_marker(cr_negative), "-")


def positive_sign_markers(cr_negative: bool) -> tuple[str, str]:
    """Return the positive markers: the positive CR/DR token plus the plus sign."""
    return (positive_word_marker(cr_negative), "+")


def _sign_marker_detection_pattern() -> str:
    escaped = sorted(
        (re.escape(t.lower()) for t in KNOWN_SIGN_MARKERS), key=len, reverse=True
    )
    return r"(?<=[0-9])\s*(" + "|".join(escaped) + r")\s*$"


SIGN_MARKER_DETECTION_RE = re.compile(_sign_marker_detection_pattern(), re.IGNORECASE)


def has_marker(trimmed: str, marker: str) -> str:
    """Return a SQL boolean expression: true when ``trimmed`` starts or ends with ``marker``."""
    m = re.escape(marker.lower())
    at_start = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^{m}\s*.+$')})"
    at_end = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^.+\s*{m}$')})"
    return f"({at_start} OR {at_end})"


def strip_marker(trimmed: str, marker: str) -> str:
    """Return a SQL expression stripping ``marker`` from the start or end of ``trimmed``."""
    m = re.escape(marker.lower())
    at_start = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^{m}\s*.+$')})"
    from_start = f"TRIM(REGEXP_REPLACE(LOWER({trimmed}), {quote_string(rf'^{m}\s*')}, ''))"
    from_end = f"TRIM(REGEXP_REPLACE(LOWER({trimmed}), {quote_string(rf'\s*{m}$')}, ''))"
    return f"CASE WHEN {at_start} THEN {from_start} ELSE {from_end} END"
