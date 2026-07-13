"""Profiling-phase issue builders."""

from __future__ import annotations

from shared.models.issues import IssueSeverity, NormalizationIssue
from shared.models.profiling import (
    ColumnProfile,
    IdentifierColumnProfile,
    MixedNumberFormatProfile,
    SymbolDistributionProfile,
)

from profiling.constants import (
    ISSUE_CODE_IDENTIFIER_DUPLICATES,
    ISSUE_CODE_MIXED_CURRENCY,
    ISSUE_CODE_MIXED_NUMBER_FORMAT,
)


def collect_column_issues(
    column_name: str,
    profile: ColumnProfile,
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

    if isinstance(profile, IdentifierColumnProfile) and profile.duplicate_count > 0:
        issues.append(
            build_identifier_duplicates_issue(
                column_name=column_name,
                duplicate_count=profile.duplicate_count,
                uniqueness_ratio=profile.uniqueness_ratio,
                distinct_count=profile.distinct_count,
            )
        )

    if isinstance(profile, MixedNumberFormatProfile) and profile.mixed_number_format_detected:
        issues.append(
            build_mixed_number_format_issue(
                column_name=column_name,
                comma_decimal_count=profile.comma_decimal_count,
                dot_decimal_count=profile.dot_decimal_count,
            )
        )

    return issues


def build_identifier_duplicates_issue(
    column_name: str,
    duplicate_count: int,
    uniqueness_ratio: float,
    distinct_count: int,
) -> NormalizationIssue:
    return NormalizationIssue(
        code=ISSUE_CODE_IDENTIFIER_DUPLICATES,
        severity=IssueSeverity.WARNING,
        message=f"Identifier column {column_name!r} contains duplicate values",
        location=column_name,
        evidence={
            "duplicate_count": duplicate_count,
            "distinct_count": distinct_count,
            "uniqueness_ratio": uniqueness_ratio,
        },
    )


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


def build_mixed_number_format_issue(
    column_name: str,
    comma_decimal_count: int,
    dot_decimal_count: int,
) -> NormalizationIssue:
    """Report a column carrying both european and western decimal notation.

    Informational: the parser resolves each value's separator individually, so
    both notations normalize correctly. The warning exists because a column that
    mixes locales is usually a sign of an upstream merge worth knowing about.
    """
    return NormalizationIssue(
        code=ISSUE_CODE_MIXED_NUMBER_FORMAT,
        severity=IssueSeverity.INFO,
        message=(
            f"Column {column_name!r} mixes decimal notations "
            f"({comma_decimal_count} comma-decimal, {dot_decimal_count} dot-decimal); "
            "each value is parsed on its own notation"
        ),
        location=column_name,
        evidence={
            "comma_decimal_count": comma_decimal_count,
            "dot_decimal_count": dot_decimal_count,
        },
    )
