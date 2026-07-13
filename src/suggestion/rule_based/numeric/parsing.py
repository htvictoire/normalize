"""Numeric token parsing: currency stripping, sign normalization, locale resolution.

Mirrors the per-value locale rules in ``shared.parsing.numeric`` so the type the
suggester infers is the type the conversion SQL can actually produce.
"""

from __future__ import annotations

import re

from shared.parsing.currency import CURRENCY_DETECTION_RE
from shared.parsing.markers import SIGN_MARKER_DETECTION_RE
from shared.parsing.numeric import decimal_pattern_regex, strip_group_only_chars

from suggestion.rule_based.models import NumericParseResult

_DECIMAL_RE = re.compile(decimal_pattern_regex())
_ZERO_INTEGER_RE = re.compile(r"^[+-]?0?$")
_GROUP_SIZE = 3


def _strip_numeric_sign(value: str) -> tuple[str, bool] | None:
    stripped = value.strip()
    if not stripped:
        return None

    if stripped.startswith("(") and stripped.endswith(")"):
        stripped = stripped[1:-1]
    if stripped.startswith(("+", "-")):
        stripped = stripped[1:]
    if stripped.endswith(("+", "-")):
        stripped = stripped[:-1]
    has_percentage = stripped.endswith("%")
    if has_percentage:
        stripped = stripped[:-1]
    stripped = strip_group_only_chars(stripped).strip()
    if not stripped:
        return None
    return stripped, has_percentage


def _lone_separator_is_decimal(value: str, index: int) -> bool:
    """Rules 3 and 4: a single separator is a decimal unless it groups thousands."""
    tail_length = len(value) - index - 1
    return tail_length != _GROUP_SIZE or bool(_ZERO_INTEGER_RE.fullmatch(value[:index]))


def resolve_decimal_separator(value: str) -> str | None:
    """Return the decimal separator this value uses, or None when it has none."""
    last_dot = value.rfind(".")
    last_comma = value.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        return "." if last_dot > last_comma else ","
    if last_comma >= 0 and value.count(",") == 1 and _lone_separator_is_decimal(value, last_comma):
        return ","
    if last_dot >= 0 and value.count(".") == 1 and _lone_separator_is_decimal(value, last_dot):
        return "."
    return None


def parse_numeric_token(value: str) -> NumericParseResult | None:
    """Parse one raw value, resolving its locale from its own shape.

    Strips any currency token first, then sign notation, then validates the shape
    against every supported grouping convention. Returns None if the value is not
    a number under any of them.
    """
    has_currency = CURRENCY_DETECTION_RE.search(value) is not None
    clean = CURRENCY_DETECTION_RE.sub("", value).strip() if has_currency else value

    has_signed = SIGN_MARKER_DETECTION_RE.search(clean) is not None
    if has_signed:
        clean = SIGN_MARKER_DETECTION_RE.sub("", clean).strip()
    if not has_signed and clean.strip().startswith("(") and clean.strip().endswith(")"):
        has_signed = True

    sign_result = _strip_numeric_sign(clean)
    if sign_result is None:
        return None
    stripped, has_percentage = sign_result

    if not _DECIMAL_RE.fullmatch(stripped):
        return None

    decimal_separator = resolve_decimal_separator(stripped)
    fractional_part: str | None = None
    if decimal_separator is None:
        integer_digits = stripped.replace(",", "").replace(".", "")
    else:
        grouping = "." if decimal_separator == "," else ","
        integer_raw, fractional_part = stripped.rsplit(decimal_separator, 1)
        integer_digits = integer_raw.replace(grouping, "")

    if not integer_digits:
        # A leading decimal point (".5") has no integer digits; it is a plain 0.5.
        if fractional_part is None:
            return None
        integer_digits = "0"
    if not integer_digits.isdigit():
        return None

    has_fractional_part = fractional_part is not None
    if fractional_part is not None:
        if not fractional_part.isdigit():
            return None
        normalized = f"{integer_digits}.{fractional_part}"
    else:
        normalized = integer_digits

    return NumericParseResult(
        normalized=normalized,
        has_currency=has_currency,
        has_signed=has_signed,
        has_percentage=has_percentage,
        has_fractional_part=has_fractional_part,
    )
