"""Currency-related SQL fragments for shared profile query builders."""

from __future__ import annotations

import re

from normalize.stages.shared_profiling.sql_helpers import quote_string

CURRENCY_SYMBOLS = (
    "$",
    "€",
    "£",
    "¥",
    "₹",
    "₩",
    "₪",
    "₿",
    "₺",
    "₽",
    "₴",
    "₫",
    "₦",
    "₱",
    "₭",
    "₲",
    "₡",
    "R$",
    "C$",
    "A$",
    "NZ$",
    "S$",
    "HK$",
    "MX$",
    "CN¥",
)
CURRENCY_CODES = (
    "USD",
    "EUR",
    "JPY",
    "GBP",
    "CNY",
    "CHF",
    "CAD",
    "AUD",
    "HKD",
    "SGD",
    "SEK",
    "NOK",
    "NZD",
    "MXN",
    "INR",
    "KRW",
    "BRL",
    "ZAR",
    "TRY",
    "AED",
)


def _currency_token_pattern() -> str:
    tokens = [*CURRENCY_SYMBOLS, *CURRENCY_CODES]
    escaped = sorted((re.escape(token.lower()) for token in tokens), key=len, reverse=True)
    return "(?:" + "|".join(escaped) + ")"


CURRENCY_TOKEN_PATTERN = _currency_token_pattern()


def strip_currency_affix_expr(value_expr: str) -> str:
    """Strip known currency tokens from front/back of lowercased value expression."""
    token_pattern = CURRENCY_TOKEN_PATTERN
    sign_prefix_pattern = rf"^([+-])\s*{token_pattern}\s*"
    sign_prefix_stripped = (
        f"REGEXP_REPLACE({value_expr}, {quote_string(sign_prefix_pattern)}, {quote_string(r'\1')})"
    )
    prefix_pattern = rf"^{token_pattern}\s*"
    prefix_stripped = f"REGEXP_REPLACE({sign_prefix_stripped}, {quote_string(prefix_pattern)}, '')"
    suffix_pattern = rf"\s*{token_pattern}$"
    suffix_stripped = f"REGEXP_REPLACE({prefix_stripped}, {quote_string(suffix_pattern)}, '')"
    return f"TRIM({suffix_stripped})"


def apply_accounting_sign_expr(value_expr: str) -> str:
    """Normalize accounting negative notation into a leading-sign numeric string."""
    trimmed = f"TRIM({value_expr})"
    parenthesized_inner = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
    parenthesized_inner_stripped = strip_currency_affix_expr(parenthesized_inner)
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


def accounting_negative_predicate(value_expr: str) -> str:
    """Predicate checking whether value carries accounting style negative notation."""
    trimmed = f"TRIM({value_expr})"
    return (
        f"REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
        f"OR REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+-$')}) "
        f"OR REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+\s+(?:cr|dr)$')})"
    )


def currency_marker_predicate(lower_value_expr: str) -> str:
    """Cheap marker predicate for currency-like rows before expensive transforms."""
    contains_token = rf"^.*(?:{CURRENCY_TOKEN_PATTERN}).*$"
    accounting = r"^\(.*\)$|^.*-$|^.*\s+(?:cr|dr)$"
    full_pattern = rf"{contains_token}|{accounting}"
    return f"REGEXP_FULL_MATCH({lower_value_expr}, {quote_string(full_pattern)})"
