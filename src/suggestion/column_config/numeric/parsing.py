"""Numeric token parsing: currency stripping, sign normalization, grouping validation."""

from __future__ import annotations

from shared.models.column import GroupingStyle
from shared.utils.currency import CURRENCY_DETECTION_RE
from shared.utils.sign_markers import SIGN_MARKER_DETECTION_RE
from suggestion.constants import (
    GROUP_FIRST_MAX_DIGITS,
    GROUP_INDIAN_MIDDLE_SIZE,
    GROUP_INDIAN_TWO_GROUP_CASE,
    GROUP_WESTERN_SIZE,
)
from suggestion.models import NumericCandidate, NumericParseResult


def _valid_group_sizes(groups: list[str], grouping_style: GroupingStyle) -> bool:
    if grouping_style == "western":
        return all(len(group) == GROUP_WESTERN_SIZE for group in groups[1:])
    if len(groups[-1]) != GROUP_WESTERN_SIZE:
        return False
    if len(groups) == GROUP_INDIAN_TWO_GROUP_CASE:
        return True
    return all(len(group) == GROUP_INDIAN_MIDDLE_SIZE for group in groups[1:-1])


def _valid_grouping(
    integer_part: str,
    *,
    thousand_separator: str,
    grouping_style: GroupingStyle,
) -> bool:
    if not integer_part:
        return True
    if not thousand_separator or thousand_separator not in integer_part:
        return integer_part.isdigit()

    groups = integer_part.split(thousand_separator)
    if any((not group) or (not group.isdigit()) for group in groups):
        return False
    if not 1 <= len(groups[0]) <= GROUP_FIRST_MAX_DIGITS:
        return False
    return _valid_group_sizes(groups, grouping_style)


def _strip_numeric_sign(value: str) -> tuple[str, bool] | None:
    stripped = value.strip().replace(" ", "")
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
    if not stripped:
        return None
    return stripped, has_percentage


def parse_numeric_token(
    value: str,
    *,
    candidate: NumericCandidate,
) -> NumericParseResult | None:
    """Parse one raw value under one candidate format.

    Strips any currency token first, then strips sign notation, then validates
    grouping and decimal structure. Returns None if the value does not parse.
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

    decimal_separator = candidate.decimal_separator
    thousand_separator = candidate.thousand_separator
    used_decimal_separator = decimal_separator in stripped
    used_thousand_separator = bool(thousand_separator) and thousand_separator in stripped
    leading_decimal_point = False

    parse_ok = stripped.count(decimal_separator) <= 1
    integer_part_raw = stripped
    fractional_part: str | None = None
    if parse_ok and decimal_separator in stripped:
        integer_part_raw, fractional_part = stripped.split(decimal_separator, 1)

    if parse_ok and not _valid_grouping(
        integer_part_raw,
        thousand_separator=thousand_separator,
        grouping_style=candidate.grouping_style,
    ):
        parse_ok = False

    integer_digits = (
        integer_part_raw.replace(thousand_separator, "")
        if thousand_separator
        else integer_part_raw
    )
    if parse_ok and not integer_digits and fractional_part is None:
        parse_ok = False
    elif parse_ok and not integer_digits:
        leading_decimal_point = True
        integer_digits = "0"
    if parse_ok and not integer_digits.isdigit():
        parse_ok = False

    has_fractional_part = fractional_part is not None
    if fractional_part is not None:
        if parse_ok and fractional_part and fractional_part.isdigit():
            normalized = f"{integer_digits}.{fractional_part}"
        else:
            return None
    elif parse_ok:
        normalized = integer_digits
    else:
        return None

    return NumericParseResult(
        normalized=normalized,
        has_currency=has_currency,
        has_signed=has_signed,
        has_percentage=has_percentage,
        has_fractional_part=has_fractional_part,
        used_decimal_separator=used_decimal_separator,
        used_thousand_separator=used_thousand_separator,
        leading_decimal_point=leading_decimal_point,
    )
