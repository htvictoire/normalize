"""Shared currency symbol/code SQL helpers."""

from __future__ import annotations

import re

from shared.db.sql import quote_string

KNOWN_CURRENCY_SYMBOLS: tuple[str, ...] = (
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
KNOWN_CURRENCY_CODES: tuple[str, ...] = (
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
    lowered_trimmed = f"LOWER(TRIM({value_expr}))"
    token_pattern = CURRENCY_TOKEN_PATTERN_LOWER
    prefix_extract = (
        f"REGEXP_EXTRACT({lowered_trimmed}, "
        f"{quote_string(rf'^[+-]?\\s*({token_pattern})\\s*.+$')}, 1)"
    )
    suffix_extract = (
        f"REGEXP_EXTRACT({lowered_trimmed}, "
        f"{quote_string(rf'^.+\\s*({token_pattern})$')}, 1)"
    )
    symbol_candidate = (
        f"COALESCE(NULLIF({prefix_extract}, ''), NULLIF({suffix_extract}, ''))"
    )
    return (
        "CASE "
        f"WHEN NULLIF(TRIM({value_expr}), '') IS NULL THEN NULL "
        f"WHEN {symbol_candidate} IS NULL THEN NULL "
        f"ELSE UPPER({symbol_candidate}) END"
    )


def _currency_token_pattern_lower() -> str:
    tokens = [token.lower() for token in _canonical_currency_tokens()]
    escaped = sorted((re.escape(token) for token in tokens), key=len, reverse=True)
    return "(?:" + "|".join(escaped) + ")"


def _canonical_currency_tokens() -> tuple[str, ...]:
    return (*KNOWN_CURRENCY_SYMBOLS, *KNOWN_CURRENCY_CODES)


CURRENCY_TOKEN_PATTERN_LOWER = _currency_token_pattern_lower()
CURRENCY_DETECTION_RE = re.compile(CURRENCY_TOKEN_PATTERN_LOWER, re.IGNORECASE)
