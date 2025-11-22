"""Config-driven SQL value preprocessor — the single source of truth for value normalization.

Each ColumnConfig type has one canonical preprocess expression returned by
``build_value_candidate_expr``.  Both the profiling and conversion packages call
this function so their SQL expressions are always derived from the same logic.

The returned expression is a SQL VARCHAR expression that:
- strips type-specific outer tokens (currency symbols, sign markers, %)
- resolves sign into a leading ``-`` where applicable
- is ready for decimal/integer pattern matching and separator replacement

Types that need no preprocessing (string, boolean, integer, decimal, date) get
back a plain ``TRIM(value_expr)``.
"""

from __future__ import annotations

import re

from shared.db.sql import quote_string
from shared.models.column import (
    AccountingColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
)
from shared.utils.currency import CURRENCY_TOKEN_PATTERN_LOWER


def build_value_candidate_expr(value_expr: str, config: ColumnConfig) -> str:
    """Return a SQL expression that preprocesses a raw value for type matching.

    For sign-bearing types (accounting, signed) sign markers are resolved into
    a leading ``-`` before any currency stripping occurs, so markers such as
    CR/DR are always detected from the config before the currency symbol
    pattern has a chance to consume them.
    """
    trimmed = f"TRIM({value_expr})"
    if isinstance(config, AccountingColumnConfig):
        return _accounting_candidate(trimmed, config)
    if isinstance(config, SignedColumnConfig):
        return _signed_candidate(trimmed, config)
    if isinstance(config, CurrencyColumnConfig):
        return _currency_candidate(trimmed)
    if isinstance(config, PercentageColumnConfig):
        return f"TRIM(REGEXP_REPLACE({trimmed}, {quote_string(r'\s*%\s*$')}, ''))"
    return trimmed


# ---------------------------------------------------------------------------
# Currency symbol stripping
# ---------------------------------------------------------------------------


def _strip_currency_symbols(value_expr: str) -> str:
    """Strip a known currency token from either end of a SQL value expression."""
    tp = CURRENCY_TOKEN_PATTERN_LOWER
    lowered = f"LOWER({value_expr})"
    sign_pat = quote_string(rf"^([+-])\s*{tp}\s*")
    sign_prefix = f"REGEXP_REPLACE({lowered}, {sign_pat}, {quote_string(r'\\1')})"
    prefix_stripped = f"REGEXP_REPLACE({sign_prefix}, {quote_string(rf'^{tp}\s*')}, '')"
    suffix_stripped = f"REGEXP_REPLACE({prefix_stripped}, {quote_string(rf'\s*{tp}$')}, '')"
    return f"TRIM({suffix_stripped})"


def _normalize_structural_sign(value_expr: str) -> str:
    """Normalize structural sign notation: ``(value)`` → ``-value``, ``value-`` → ``-value``."""
    trimmed = f"TRIM({value_expr})"
    inner_paren = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
    inner_trailing = f"TRIM(SUBSTRING({trimmed}, 1, LENGTH({trimmed}) - 1))"
    return (
        "CASE "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
        f"THEN '-' || {_strip_currency_symbols(inner_paren)} "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+-$')}) "
        f"THEN '-' || {inner_trailing} "
        f"ELSE {trimmed} END"
    )


# ---------------------------------------------------------------------------
# Sign marker helpers
# ---------------------------------------------------------------------------


def _has_marker(trimmed: str, marker: str) -> str:
    m = re.escape(marker.lower())
    at_start = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^{m}\s*.+$')})"
    at_end = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^.+\s*{m}$')})"
    return f"({at_start} OR {at_end})"


def _strip_marker(trimmed: str, marker: str) -> str:
    m = re.escape(marker.lower())
    at_start = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^{m}\s*.+$')})"
    from_start = f"TRIM(REGEXP_REPLACE(LOWER({trimmed}), {quote_string(rf'^{m}\s*')}, ''))"
    from_end = f"TRIM(REGEXP_REPLACE(LOWER({trimmed}), {quote_string(rf'\s*{m}$')}, ''))"
    return f"CASE WHEN {at_start} THEN {from_start} ELSE {from_end} END"


# ---------------------------------------------------------------------------
# Per-type candidate builders
# ---------------------------------------------------------------------------


def _currency_candidate(trimmed: str) -> str:
    """Currency: strip symbols, then normalize structural sign notation."""
    return _normalize_structural_sign(_strip_currency_symbols(trimmed))


def _signed_candidate(trimmed: str, config: SignedColumnConfig) -> str:
    """Signed: apply sign markers from config only — no currency symbol stripping."""
    cases = []
    for marker in config.negative_markers:
        stripped = _strip_marker(trimmed, marker)
        cases.append(f"WHEN {_has_marker(trimmed, marker)} THEN '-' || TRIM({stripped})")
    for marker in config.positive_markers:
        stripped = _strip_marker(trimmed, marker)
        cases.append(f"WHEN {_has_marker(trimmed, marker)} THEN TRIM({stripped})")
    if config.parentheses_as_negative:
        inner = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
        cases.append(
            f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
            f"THEN '-' || {inner}"
        )
    if not cases:
        return trimmed
    return "CASE " + " ".join(cases) + f" ELSE {trimmed} END"


def _accounting_candidate(trimmed: str, config: AccountingColumnConfig) -> str:
    """Accounting: sign markers take priority over currency stripping.

    For each marker the value is matched against the config markers first,
    the marker is stripped, then currency symbols are stripped from the
    remainder, and the sign is prepended.  This ordering ensures that text
    markers such as CR/DR are consumed from the config before the global
    currency symbol pattern has a chance to remove them.

    The ELSE branch (no marker matched) strips currency symbols and normalises
    structural sign notation (parentheses, trailing minus).
    """
    cases = []
    for marker in config.negative_markers:
        stripped = _strip_currency_symbols(_strip_marker(trimmed, marker))
        cases.append(f"WHEN {_has_marker(trimmed, marker)} THEN '-' || {stripped}")
    for marker in config.positive_markers:
        stripped = _strip_currency_symbols(_strip_marker(trimmed, marker))
        cases.append(f"WHEN {_has_marker(trimmed, marker)} THEN {stripped}")
    if config.parentheses_as_negative:
        inner = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
        inner_stripped = _strip_currency_symbols(inner)
        cases.append(
            f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
            f"THEN '-' || {inner_stripped}"
        )
    else_expr = _normalize_structural_sign(_strip_currency_symbols(trimmed))
    if not cases:
        return else_expr
    return "CASE " + " ".join(cases) + f" ELSE {else_expr} END"
