"""Shared currency symbol/code SQL helpers."""

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


def _currency_token_pattern_lower() -> str:
    tokens = [token.lower() for token in KNOWN_CURRENCY_TOKENS]
    escaped = sorted((re.escape(token) for token in tokens), key=len, reverse=True)
    return "(?:" + "|".join(escaped) + ")"


CURRENCY_TOKEN_PATTERN_LOWER = _currency_token_pattern_lower()
CURRENCY_DETECTION_RE = re.compile(CURRENCY_TOKEN_PATTERN_LOWER, re.IGNORECASE)