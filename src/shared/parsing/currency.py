"""Currency symbol/code constants and SQL expression helpers."""

from __future__ import annotations

import re

from shared.db.sql import quote_string

KNOWN_CURRENCY_TOKENS: tuple[str, ...] = (
    # Symbols
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
    "AU$",
    "NZ$",
    "S$",
    "HK$",
    "MX$",
    "CN¥",
    # ISO codes
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


def _currency_token_pattern_lower() -> str:
    tokens = [token.lower() for token in KNOWN_CURRENCY_TOKENS]
    escaped = sorted((re.escape(token) for token in tokens), key=len, reverse=True)
    return "(?:" + "|".join(escaped) + ")"


CURRENCY_TOKEN_PATTERN_LOWER = _currency_token_pattern_lower()
CURRENCY_DETECTION_RE = re.compile(CURRENCY_TOKEN_PATTERN_LOWER, re.IGNORECASE)


def build_currency_symbol_extract_expr(value_expr: str) -> str:
    """Extract the leading or trailing currency token when present."""
    trimmed = f"TRIM({value_expr})"
    inner = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
    paren_stripped = (
        f"CASE WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
        f"THEN {inner} ELSE {trimmed} END"
    )
    lowered = f"LOWER({paren_stripped})"
    token_pattern = CURRENCY_TOKEN_PATTERN_LOWER
    prefix_extract = (
        f"REGEXP_EXTRACT({lowered}, "
        f"{quote_string(rf'^[+-]?\\s*({token_pattern})\\s*.+$')}, 1)"
    )
    suffix_extract = (
        f"REGEXP_EXTRACT({lowered}, "
        f"{quote_string(rf'^.+\\s*({token_pattern})$')}, 1)"
    )
    symbol_candidate = (
        f"COALESCE(NULLIF({prefix_extract}, ''), NULLIF({suffix_extract}, ''))"
    )
    return (
        "CASE "
        f"WHEN NULLIF({trimmed}, '') IS NULL THEN NULL "
        f"WHEN {symbol_candidate} IS NULL THEN NULL "
        f"ELSE UPPER({symbol_candidate}) END"
    )


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
