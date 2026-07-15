"""Profiling-phase issue builders."""

from __future__ import annotations

from shared.models.column import (
    ColumnConfig,
    DateColumnConfig,
    DateTimeColumnConfig,
    IdentifierColumnConfig,
)
from shared.models.column.specs import has_signed_notation
from shared.models.issues import (
    DateOrderAmbiguousEvidence,
    DateOrderAmbiguousIssue,
    IdentifierDuplicatesEvidence,
    IdentifierDuplicatesIssue,
    IssueSeverity,
    MixedCurrencyEvidence,
    MixedCurrencyIssue,
    MixedNumberFormatEvidence,
    MixedNumberFormatIssue,
    MultiplePrimaryKeysEvidence,
    MultiplePrimaryKeysIssue,
    NormalizationIssue,
    PreambleRowsSkippedEvidence,
    PreambleRowsSkippedIssue,
    SignMarkerConventionEvidence,
    SignMarkerConventionIssue,
)
from shared.models.operation import CsvSourceFormat, ExcelSourceFormat, SourceFormat
from shared.models.profiling import (
    AccountingColumnProfile,
    ColumnProfile,
    DayMonthOrderProfile,
    IdentifierColumnProfile,
    MixedNumberFormatProfile,
    SymbolDistributionProfile,
)
from shared.parsing.markers import negative_word_marker, positive_word_marker


def _preamble_row_count(source_format: SourceFormat) -> int:
    """Return the number of rows dropped at ingestion because they precede the header."""
    if not isinstance(source_format, CsvSourceFormat | ExcelSourceFormat):
        return 0
    if source_format.header_mode != "present" or source_format.header_row_index is None:
        return 0
    return source_format.header_row_index - 1


def collect_dataset_issues(
    column_config: dict[str, ColumnConfig],
    source_format: SourceFormat,
) -> list[NormalizationIssue]:
    """Return issues detected from the config as a whole, not from any one column."""
    issues: list[NormalizationIssue] = []

    skipped_count = _preamble_row_count(source_format)
    if skipped_count > 0:
        issues.append(build_preamble_rows_skipped_issue(skipped_count))

    primary_keys = [
        name
        for name, config in column_config.items()
        if isinstance(config, IdentifierColumnConfig) and config.identifier_kind == "primary"
    ]
    if len(primary_keys) > 1:
        issues.append(build_multiple_primary_keys_issue(sorted(primary_keys)))

    return issues


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

    if (
        isinstance(profile, DayMonthOrderProfile)
        and isinstance(config, DateColumnConfig | DateTimeColumnConfig)
        and profile.order_ambiguous_count > 0
        and profile.order_decisive_count == 0
    ):
        issues.append(
            build_date_order_ambiguous_issue(
                column_name=column_name,
                day_first=config.day_first,
                order_ambiguous_count=profile.order_ambiguous_count,
                order_decisive_count=profile.order_decisive_count,
            )
        )

    if isinstance(profile, AccountingColumnProfile) and has_signed_notation(config):
        negative_marker = negative_word_marker(config.cr_negative)
        positive_marker = positive_word_marker(config.cr_negative)
        negative_count = profile.negative_marker_distribution.get(negative_marker, 0)
        positive_count = profile.positive_marker_distribution.get(positive_marker, 0)
        if negative_count > 0 or positive_count > 0:
            issues.append(
                build_sign_marker_convention_issue(
                    column_name=column_name,
                    cr_negative=config.cr_negative,
                    negative_marker=negative_marker,
                    positive_marker=positive_marker,
                    negative_marker_count=negative_count,
                    positive_marker_count=positive_count,
                )
            )

    return issues


def build_preamble_rows_skipped_issue(skipped_count: int) -> PreambleRowsSkippedIssue:
    """Rows above the header row, dropped at ingestion.

    Informational: the header marks where the table begins, so preceding rows are not
    data. Reported because a misdetected header row deletes real rows with no other trace.
    """
    rows = "1 row was" if skipped_count == 1 else f"{skipped_count} rows were"
    return PreambleRowsSkippedIssue(
        severity=IssueSeverity.INFO,
        message=(
            f"{rows} skipped as preamble above the header; "
            "verify the header row if the source was not expected to have one"
        ),
        evidence=PreambleRowsSkippedEvidence(
            skipped_count=skipped_count,
            header_row_index=skipped_count + 1,
        ),
    )


def build_multiple_primary_keys_issue(column_names: list[str]) -> MultiplePrimaryKeysIssue:
    """A dataset has one primary key. Two declared keys means neither can be trusted."""
    return MultiplePrimaryKeysIssue(
        severity=IssueSeverity.ERROR,
        message=(
            f"{len(column_names)} columns are declared primary keys "
            f"({', '.join(repr(name) for name in column_names)}); a dataset has one"
        ),
        evidence=MultiplePrimaryKeysEvidence(columns=column_names),
    )


def build_identifier_duplicates_issue(
    column_name: str,
    is_primary_key: bool,
    duplicate_count: int,
    uniqueness_ratio: float,
    distinct_count: int,
) -> IdentifierDuplicatesIssue:
    """Duplicate identifier values.

    ERROR on a primary key: uniqueness is the whole contract, and a consumer joining
    on it will silently multiply rows. WARNING on any other identifier kind, where
    repetition is expected (a foreign key repeats by definition).
    """
    kind = "Primary key" if is_primary_key else "Identifier"
    return IdentifierDuplicatesIssue(
        severity=IssueSeverity.ERROR if is_primary_key else IssueSeverity.WARNING,
        message=f"{kind} column {column_name!r} contains duplicate values",
        location=column_name,
        evidence=IdentifierDuplicatesEvidence(
            is_primary_key=is_primary_key,
            duplicate_count=duplicate_count,
            distinct_count=distinct_count,
            uniqueness_ratio=uniqueness_ratio,
        ),
    )


def build_mixed_currency_issue(
    column_name: str,
    symbols: list[str],
    symbol_detected_ratio: float,
    dominant_symbol: str | None,
    dominant_symbol_ratio: float,
) -> MixedCurrencyIssue:
    return MixedCurrencyIssue(
        severity=IssueSeverity.WARNING,
        message=f"Column {column_name!r} contains mixed currency symbols",
        location=column_name,
        evidence=MixedCurrencyEvidence(
            symbols=symbols,
            symbol_detected_ratio=symbol_detected_ratio,
            dominant_symbol=dominant_symbol,
            dominant_symbol_ratio=dominant_symbol_ratio,
        ),
    )


def build_date_order_ambiguous_issue(
    column_name: str,
    day_first: bool,
    order_ambiguous_count: int,
    order_decisive_count: int,
) -> DateOrderAmbiguousIssue:
    """Every order-bearing value parses under both day/month orders.

    Warned because the confirmed day_first setting is then the only thing
    deciding the dates: a wrong setting transposes day and month while parsing
    cleanly.
    """
    order = "day-first" if day_first else "month-first"
    return DateOrderAmbiguousIssue(
        severity=IssueSeverity.WARNING,
        message=(
            f"Column {column_name!r} has {order_ambiguous_count} day/month-ambiguous "
            f"values and none that prove the order; all are read {order} per the "
            "confirmed day_first setting"
        ),
        location=column_name,
        evidence=DateOrderAmbiguousEvidence(
            day_first=day_first,
            order_ambiguous_count=order_ambiguous_count,
            order_decisive_count=order_decisive_count,
        ),
    )


def build_sign_marker_convention_issue(
    column_name: str,
    cr_negative: bool,
    negative_marker: str,
    positive_marker: str,
    negative_marker_count: int,
    positive_marker_count: int,
) -> SignMarkerConventionIssue:
    """CR/DR polarity is a declared convention, not derivable from the values.

    Warned so a consumer can verify the applied convention before trusting the
    signs: a flipped convention negates every marked amount while parsing
    cleanly.
    """
    return SignMarkerConventionIssue(
        severity=IssueSeverity.WARNING,
        message=(
            f"Column {column_name!r} carries {negative_marker}/{positive_marker} sign "
            f"markers; {negative_marker} is read as negative and {positive_marker} as "
            "positive per the confirmed cr_negative setting"
        ),
        location=column_name,
        evidence=SignMarkerConventionEvidence(
            cr_negative=cr_negative,
            negative_marker=negative_marker,
            positive_marker=positive_marker,
            negative_marker_count=negative_marker_count,
            positive_marker_count=positive_marker_count,
        ),
    )


def build_mixed_number_format_issue(
    column_name: str,
    comma_decimal_count: int,
    dot_decimal_count: int,
) -> MixedNumberFormatIssue:
    """Report a column carrying both european and western decimal notation.

    Informational: each value is parsed on its own notation, so both normalize
    correctly. A column that mixes locales usually indicates an upstream merge.
    """
    return MixedNumberFormatIssue(
        severity=IssueSeverity.INFO,
        message=(
            f"Column {column_name!r} mixes decimal notations "
            f"({comma_decimal_count} comma-decimal, {dot_decimal_count} dot-decimal); "
            "each value is parsed on its own notation"
        ),
        location=column_name,
        evidence=MixedNumberFormatEvidence(
            comma_decimal_count=comma_decimal_count,
            dot_decimal_count=dot_decimal_count,
        ),
    )
