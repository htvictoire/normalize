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


def build_accounting_negative_predicate(value_expr: str) -> str:
    """Match accounting-style negative notations on a SQL value expression."""
    trimmed = f"TRIM({value_expr})"
    return (
        f"REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
        f"OR REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+-$')}) "
        f"OR REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+\s+(?:cr|dr)$')})"
    )


def build_accounting_normalized_expr(value_expr: str) -> str:
    """Normalize accounting-style negative markers into signed decimal text."""
    trimmed = f"TRIM({value_expr})"
    parenthesized_inner = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
    parenthesized_inner_stripped = build_currency_symbol_stripped_expr(parenthesized_inner)
    trailing_minus_inner = f"TRIM(SUBSTRING({trimmed}, 1, LENGTH({trimmed}) - 1))"
    trailing_cr_inner = f"TRIM(REGEXP_REPLACE({trimmed}, {quote_string(r'\s+cr$')}, ''))"
    trailing_dr_inner = f"TRIM(REGEXP_REPLACE({trimmed}, {quote_string(r'\s+dr$')}, ''))"
    return (
        "CASE "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
        f"THEN '-' || {parenthesized_inner_stripped} "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+-$')}) "
        f"THEN '-' || {trailing_minus_inner} "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+\s+cr$')}) "
        f"THEN '-' || {trailing_cr_inner} "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+\s+dr$')}) "
        f"THEN {trailing_dr_inner} "
        f"ELSE {trimmed} END"
    )


def build_currency_numeric_candidate_expr(value_expr: str) -> str:
    """Normalize currency text into sign+digits text before separator replacement."""
    symbol_stripped = build_currency_symbol_stripped_expr(value_expr)
    return build_accounting_normalized_expr(symbol_stripped)
