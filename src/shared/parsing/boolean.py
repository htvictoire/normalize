"""Canonical boolean vocabulary shared by suggestion, profiling, and conversion.

Boolean columns carry no per-column tokens; every one is matched against this fixed
set. Tokens are authored lowercase to match ``LOWER(TRIM(value))`` on the SQL side
and ``value.strip().lower()`` in Python. Each pair is ``(true_token, false_token)``.
"""

from __future__ import annotations

BOOLEAN_TOKEN_PAIRS: tuple[tuple[str, str], ...] = (
    # English and generic
    ("true", "false"),
    ("yes", "no"),
    ("1", "0"),
    ("t", "f"),
    ("y", "n"),
    ("on", "off"),
    # Domain conventions read as boolean
    ("active", "inactive"),
    ("enabled", "disabled"),
    ("checked", "unchecked"),
    ("pass", "fail"),
    ("ok", "nok"),
    ("paid", "unpaid"),
    # Common non-English encodings
    ("oui", "non"),  # French
    ("si", "no"),  # Spanish / Italian (false "no" shared with English)
    ("ja", "nein"),  # German
    ("sim", "nao"),  # Portuguese
    ("vero", "falso"),  # Italian
    ("wahr", "falsch"),  # German
)

BOOLEAN_TRUE_TOKENS: frozenset[str] = frozenset(t for t, _ in BOOLEAN_TOKEN_PAIRS)
BOOLEAN_FALSE_TOKENS: frozenset[str] = frozenset(f for _, f in BOOLEAN_TOKEN_PAIRS)

# The sides must stay disjoint: an overlapping token would always resolve to TRUE.
_OVERLAP = BOOLEAN_TRUE_TOKENS & BOOLEAN_FALSE_TOKENS
if _OVERLAP:
    raise ValueError(f"boolean token appears as both true and false: {sorted(_OVERLAP)}")
