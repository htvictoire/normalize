"""Config-driven SQL value preprocessor — the single source of truth for value normalization.

Each ColumnConfig type has one canonical preprocess expression returned by
``build_value_candidate_expr``.  Both the profiling and conversion packages call
this function so their SQL expressions are always derived from the same logic.

The returned expression is a SQL VARCHAR expression that:
- strips type-specific outer tokens (currency symbols, sign markers, %)
- resolves sign into a leading ``-`` where applicable
- is ready for decimal/integer pattern matching and separator replacement

Types that need no preprocessing (string, boolean, integer, date, datetime, time) get
back a plain ``TRIM(value_expr)``.
"""

from __future__ import annotations

from shared.db.sql import quote_string
from shared.models.column import (
    AccountingColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
)
from shared.parsing.currency import normalize_structural_sign, strip_currency_symbols
from shared.parsing.markers import (
    has_marker,
    negative_sign_markers,
    positive_sign_markers,
    strip_marker,
)


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


def _currency_candidate(trimmed: str) -> str:
    return normalize_structural_sign(strip_currency_symbols(trimmed))


def _signed_candidate(trimmed: str, config: SignedColumnConfig) -> str:
    cases = []
    for marker in negative_sign_markers(config.cr_negative):
        stripped = strip_marker(trimmed, marker)
        cases.append(f"WHEN {has_marker(trimmed, marker)} THEN '-' || TRIM({stripped})")
    for marker in positive_sign_markers(config.cr_negative):
        stripped = strip_marker(trimmed, marker)
        cases.append(f"WHEN {has_marker(trimmed, marker)} THEN TRIM({stripped})")
    inner = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
    cases.append(
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
        f"THEN '-' || {inner}"
    )
    return "CASE " + " ".join(cases) + f" ELSE {trimmed} END"


def _accounting_candidate(trimmed: str, config: AccountingColumnConfig) -> str:
    """Accounting: sign markers take priority over currency stripping.

    Markers are consumed before the global currency symbol pattern has a
    chance to remove them (prevents CR/DR being treated as currency tokens).
    """
    cases = []
    for marker in negative_sign_markers(config.cr_negative):
        stripped = strip_currency_symbols(strip_marker(trimmed, marker))
        cases.append(f"WHEN {has_marker(trimmed, marker)} THEN '-' || {stripped}")
    for marker in positive_sign_markers(config.cr_negative):
        stripped = strip_currency_symbols(strip_marker(trimmed, marker))
        cases.append(f"WHEN {has_marker(trimmed, marker)} THEN {stripped}")
    inner = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
    inner_stripped = strip_currency_symbols(inner)
    cases.append(
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
        f"THEN '-' || {inner_stripped}"
    )
    else_expr = normalize_structural_sign(strip_currency_symbols(trimmed))
    return "CASE " + " ".join(cases) + f" ELSE {else_expr} END"
