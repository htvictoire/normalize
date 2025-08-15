"""Profiling-phase issue builders."""

from __future__ import annotations

from shared.models.issues import IssueSeverity, NormalizationIssue

ISSUE_CODE_MIXED_CURRENCY = "MIXED_CURRENCY"
ISSUE_CODE_SEPARATOR_MISMATCH = "SEPARATOR_MISMATCH"


def build_mixed_currency_issue(
    *,
    column_name: str,
    symbols: list[str],
    dominant_symbol: str | None,
    dominant_symbol_ratio: float,
) -> NormalizationIssue:
    return NormalizationIssue(
        code=ISSUE_CODE_MIXED_CURRENCY,
        severity=IssueSeverity.WARNING,
        message=f"Column {column_name!r} contains mixed currency symbols",
        location=column_name,
        evidence={
            "symbols": symbols,
            "dominant_symbol": dominant_symbol,
            "dominant_symbol_ratio": dominant_symbol_ratio,
        },
    )


def build_separator_mismatch_issue(
    *,
    column_name: str,
    decimal_separator: str,
    thousand_separator: str,
    numeric_threshold: float,
    declared_decimal_ratio: float,
    swapped_decimal_ratio: float,
) -> NormalizationIssue:
    return NormalizationIssue(
        code=ISSUE_CODE_SEPARATOR_MISMATCH,
        severity=IssueSeverity.WARNING,
        message=(
            f"Column {column_name!r} appears numeric with swapped separators "
            f"(declared decimal={decimal_separator!r}, thousand={thousand_separator!r})"
        ),
        location=column_name,
        evidence={
            "numeric_threshold": numeric_threshold,
            "declared_decimal_ratio": declared_decimal_ratio,
            "swapped_decimal_ratio": swapped_decimal_ratio,
            "declared_separators": {
                "decimal_separator": decimal_separator,
                "thousand_separator": thousand_separator,
            },
            "suggested_separators": {
                "decimal_separator": thousand_separator,
                "thousand_separator": decimal_separator,
            },
        },
    )
