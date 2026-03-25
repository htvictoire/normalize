"""SQL expression helpers for currency symbol stripping and structural sign normalization."""

from __future__ import annotations

from shared.db.sql import quote_string
from shared.utils.currency import CURRENCY_TOKEN_PATTERN_LOWER


def strip_currency_symbols(value_expr: str) -> str:
    """Strip a known currency token from either end of a SQL value expression."""
    tp = CURRENCY_TOKEN_PATTERN_LOWER
    lowered = f"LOWER({value_expr})"
    sign_pat = quote_string(rf"^([+-])\s*{tp}\s*")
    sign_prefix = f"REGEXP_REPLACE({lowered}, {sign_pat}, {quote_string(r'\\1')})"
    prefix_stripped = f"REGEXP_REPLACE({sign_prefix}, {quote_string(rf'^{tp}\s*')}, '')"
    suffix_stripped = f"REGEXP_REPLACE({prefix_stripped}, {quote_string(rf'\s*{tp}$')}, '')"
    return f"TRIM({suffix_stripped})"


def normalize_structural_sign(value_expr: str) -> str:
    """Normalize structural sign notation: ``(value)`` → ``-value``, ``value-`` → ``-value``."""
    trimmed = f"TRIM({value_expr})"
    inner_paren = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
    inner_trailing = f"TRIM(SUBSTRING({trimmed}, 1, LENGTH({trimmed}) - 1))"
    return (
        "CASE "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
        f"THEN '-' || {strip_currency_symbols(inner_paren)} "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+-$')}) "
        f"THEN '-' || {inner_trailing} "
        f"ELSE {trimmed} END"
    )
