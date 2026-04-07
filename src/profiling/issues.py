"""Profiling-phase issue builders."""

from __future__ import annotations

from typing import cast

from shared.models.column import ColumnConfig, DecimalFamilyColumnConfig
from shared.models.issues import IssueSeverity, NormalizationIssue
from shared.models.profiling import (
    ColumnProfile,
    SeparatorMismatchProfile,
    SymbolDistributionProfile,
)

from profiling.constants import ISSUE_CODE_MIXED_CURRENCY, ISSUE_CODE_SEPARATOR_MISMATCH


def collect_column_issues(
    column_name: str,
    config: ColumnConfig,
    profile: ColumnProfile,
    numeric_threshold: float,
) -> list[NormalizationIssue]:
    """Return issues detected from the column profile."""
    issues: list[NormalizationIssue] = []

    if isinstance(profile, SymbolDistributionProfile) and profile.has_mixed_symbols:
        issues.append(
            build_mixed_currency_issue(
                column_name=column_name,
                symbols=sorted(profile.symbol_distribution.keys()),
                symbol_detected_ratio=profile.symbol_detected_ratio,
                dominant_symbol=profile.dominant_symbol,
                dominant_symbol_ratio=profile.dominant_symbol_ratio,
            )
        )

    if (
        isinstance(profile, SeparatorMismatchProfile)
        and profile.separator_mismatch_detected
        and profile.swapped_match_ratio >= numeric_threshold
    ):
        decimal_config = cast(DecimalFamilyColumnConfig, config)
        issues.append(
            build_separator_mismatch_issue(
                column_name=column_name,
                decimal_separator=decimal_config.decimal_separator,
                thousand_separator=decimal_config.thousand_separator,
                numeric_threshold=numeric_threshold,
                declared_decimal_ratio=profile.parse_match_ratio,
                swapped_decimal_ratio=profile.swapped_match_ratio,
            )
        )

    return issues


def build_mixed_currency_issue(
    column_name: str,
    symbols: list[str],
    symbol_detected_ratio: float,
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
            "symbol_detected_ratio": symbol_detected_ratio,
            "dominant_symbol": dominant_symbol,
            "dominant_symbol_ratio": dominant_symbol_ratio,
        },
    )


def build_separator_mismatch_issue(
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
