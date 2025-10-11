"""Currency SQL fragment helpers used by cell normalization transforms."""

from __future__ import annotations

from conversion.stages.cell_normalization.sql_helpers import quote_string
from shared.utils.currency import CURRENCY_TOKEN_PATTERN_LOWER


def build_currency_symbol_stripped_expr(value_expr: str) -> str:
    """Strip a known currency token from either end of a SQL value expression."""
    token_pattern = CURRENCY_TOKEN_PATTERN_LOWER
    trimmed = f"TRIM({value_expr})"
    lowered = f"LOWER({trimmed})"

    sign_prefix_pattern = rf"^([+-])\s*{token_pattern}\s*"
    sign_prefix_stripped = (
        f"REGEXP_REPLACE({lowered}, {quote_string(sign_prefix_pattern)}, {quote_string(r'\\1')})"
    )
    prefix_pattern = rf"^{token_pattern}\s*"
    prefix_stripped = f"REGEXP_REPLACE({sign_prefix_stripped}, {quote_string(prefix_pattern)}, '')"
    suffix_pattern = rf"\s*{token_pattern}$"
    suffix_stripped = f"REGEXP_REPLACE({prefix_stripped}, {quote_string(suffix_pattern)}, '')"
    return f"TRIM({suffix_stripped})"


def _build_structural_sign_expr(value_expr: str) -> str:
    """Normalize structural negatives (parentheses, trailing minus) to signed decimal text."""
    trimmed = f"TRIM({value_expr})"
    parenthesized_inner = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
    parenthesized_inner_stripped = build_currency_symbol_stripped_expr(parenthesized_inner)
    trailing_minus_inner = f"TRIM(SUBSTRING({trimmed}, 1, LENGTH({trimmed}) - 1))"
    return (
        "CASE "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
        f"THEN '-' || {parenthesized_inner_stripped} "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+-$')}) "
        f"THEN '-' || {trailing_minus_inner} "
        f"ELSE {trimmed} END"
    )


def build_currency_numeric_candidate_expr(value_expr: str) -> str:
    """Normalize currency text into sign+digits text before separator replacement."""
    symbol_stripped = build_currency_symbol_stripped_expr(value_expr)
    return _build_structural_sign_expr(symbol_stripped)
