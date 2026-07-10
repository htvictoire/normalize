"""Shared deterministic patterns for AI-only structured string configs."""

from __future__ import annotations

from shared.db.sql import quote_string

EMAIL_PATTERN = r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
URL_PATTERN = r"^https?://[^\s/$.?#].[^\s]*$"
IPV4_PATTERN = (
    r"^(?:(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})$"
)
IPV6_PATTERN = (
    r"^(?:"
    r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,7}:|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,5}(?::[0-9A-Fa-f]{1,4}){1,2}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,4}(?::[0-9A-Fa-f]{1,4}){1,3}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,3}(?::[0-9A-Fa-f]{1,4}){1,4}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,2}(?::[0-9A-Fa-f]{1,4}){1,5}|"
    r"[0-9A-Fa-f]{1,4}:(?:(?::[0-9A-Fa-f]{1,4}){1,6})|"
    r":(?:(?::[0-9A-Fa-f]{1,4}){1,7}|:)"
    r")$"
)
PHONE_PATTERN = r"^\+[1-9][0-9]{7,14}$"


def ip_address_pattern(version: str) -> str:
    """Return the SQL regex pattern for the configured IP-address version."""
    if version == "v4":
        return IPV4_PATTERN
    if version == "v6":
        return IPV6_PATTERN
    return f"(?:{IPV4_PATTERN})|(?:{IPV6_PATTERN})"


def trim_cast_expr(value_expr: str) -> str:
    """Return SQL that casts a value to text and trims surrounding whitespace."""
    return f"TRIM(CAST({value_expr} AS VARCHAR))"


def lowercase_email_expr(value_expr: str) -> str:
    """Return SQL that canonicalizes an email candidate."""
    return f"LOWER({trim_cast_expr(value_expr)})"


def phone_e164_candidate_expr(value_expr: str) -> str:
    """Return SQL that strips common phone separators before E.164-like validation."""
    return (
        f"REGEXP_REPLACE({trim_cast_expr(value_expr)}, "
        f"{quote_string(r'[\s().-]')}, '', 'g')"
    )


def regex_full_match_expr(value_expr: str, pattern: str) -> str:
    """Return a DuckDB full-regex-match predicate."""
    return f"REGEXP_FULL_MATCH({value_expr}, {quote_string(pattern)})"
