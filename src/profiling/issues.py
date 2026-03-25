"""Profiling-phase issue builders."""

from __future__ import annotations

from shared.models.column import (
    AccountingColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DecimalColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
)
from shared.models.issues import IssueSeverity, NormalizationIssue
from shared.models.profiling import (
    AccountingColumnProfile,
    ColumnProfile,
    CurrencyColumnProfile,
    DecimalColumnProfile,
    PercentageColumnProfile,
    SignedColumnProfile,
)

ISSUE_CODE_MIXED_CURRENCY = "MIXED_CURRENCY"
ISSUE_CODE_SEPARATOR_MISMATCH = "SEPARATOR_MISMATCH"

_MixedCurrencyProfile = CurrencyColumnProfile | AccountingColumnProfile
_SeparatorMismatchProfile = (
    DecimalColumnProfile
    | PercentageColumnProfile
    | SignedColumnProfile
    | CurrencyColumnProfile
    | AccountingColumnProfile
)
_SeparatorMismatchConfig = (
    DecimalColumnConfig
    | PercentageColumnConfig
    | SignedColumnConfig
    | CurrencyColumnConfig
    | AccountingColumnConfig
)


def collect_column_issues(
    column_name: str,
    config: ColumnConfig,
    profile: ColumnProfile,
    issues: list[NormalizationIssue],
    currency_ratios: list[float],
    *,
    numeric_threshold: float,
) -> None:
    """Append any data-quality issues detected from the column profile."""
    if isinstance(profile, _MixedCurrencyProfile):
        currency_ratios.append(profile.dominant_symbol_ratio)
        if profile.has_mixed_symbols:
            issues.append(
                build_mixed_currency_issue(
                    column_name=column_name,
                    symbols=sorted(profile.symbol_distribution.keys()),
                    dominant_symbol=profile.dominant_symbol,
                    dominant_symbol_ratio=profile.dominant_symbol_ratio,
                )
            )

    if (
        isinstance(profile, _SeparatorMismatchProfile)
        and isinstance(config, _SeparatorMismatchConfig)
        and profile.separator_mismatch_detected
        and profile.swapped_match_ratio >= numeric_threshold
    ):
        issues.append(
            build_separator_mismatch_issue(
                column_name=column_name,
                decimal_separator=config.decimal_separator,
                thousand_separator=config.thousand_separator,
                numeric_threshold=numeric_threshold,
                declared_decimal_ratio=profile.parse_match_ratio,
                swapped_decimal_ratio=profile.swapped_match_ratio,
            )
        )


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
