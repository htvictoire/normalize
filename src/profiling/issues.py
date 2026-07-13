"""Profiling-phase issue builders."""

from __future__ import annotations

from shared.models.column import ColumnConfig, IdentifierColumnConfig
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
    ISSUE_CODE_MULTIPLE_PRIMARY_KEYS,
)


def collect_dataset_issues(
    column_config: dict[str, ColumnConfig],
) -> list[NormalizationIssue]:
    """Return issues detected from the config as a whole, not from any one column."""
    primary_keys = [
        name
        for name, config in column_config.items()
        if isinstance(config, IdentifierColumnConfig) and config.identifier_kind == "primary"
    ]
    if len(primary_keys) > 1:
        return [build_multiple_primary_keys_issue(sorted(primary_keys))]
    return []


def collect_column_issues(
    column_name: str,
    config: ColumnConfig,
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
                is_primary_key=(
                    isinstance(config, IdentifierColumnConfig)
                    and config.identifier_kind == "primary"
                ),
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


def build_multiple_primary_keys_issue(column_names: list[str]) -> NormalizationIssue:
    """A dataset has one primary key. Two declared keys means neither can be trusted."""
    return NormalizationIssue(
        code=ISSUE_CODE_MULTIPLE_PRIMARY_KEYS,
        severity=IssueSeverity.ERROR,
        message=(
            f"{len(column_names)} columns are declared primary keys "
            f"({', '.join(repr(name) for name in column_names)}); a dataset has one"
        ),
        evidence={"columns": column_names},
    )


def build_identifier_duplicates_issue(
    column_name: str,
    is_primary_key: bool,
    duplicate_count: int,
    uniqueness_ratio: float,
    distinct_count: int,
) -> NormalizationIssue:
    """Duplicate identifier values.

    ERROR on a primary key: uniqueness is the whole contract, and a consumer joining
    on it will silently multiply rows. WARNING on any other identifier kind, where
    repetition is expected (a foreign key repeats by definition).
    """
    kind = "Primary key" if is_primary_key else "Identifier"
    return NormalizationIssue(
        code=ISSUE_CODE_IDENTIFIER_DUPLICATES,
        severity=IssueSeverity.ERROR if is_primary_key else IssueSeverity.WARNING,
        message=f"{kind} column {column_name!r} contains duplicate values",
        location=column_name,
        evidence={
            "is_primary_key": is_primary_key,
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
