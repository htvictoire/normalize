"""Profiling pipeline over the full dataset."""

from __future__ import annotations

from pathlib import Path

from conversion.stages.header_canonicalization import HeaderCanonicalizationStage
from profiling.issues import build_mixed_currency_issue, build_separator_mismatch_issue
from profiling.stats import (
    compute_boolean_column_profile,
    compute_currency_column_profile,
    compute_date_column_profile,
    compute_global_stats,
    compute_null_stats,
    compute_numeric_column_profile,
)
from shared.column_parsing.normalizer import build_value_candidate_expr
from shared.db.duckdb import DuckDBManager
from shared.db.sql import quote_identifier, read_columns
from shared.ingestion import IngestionRequest, run_ingestion
from shared.models.column import (
    AccountingColumnConfig,
    BooleanColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
    column_config_type,
)
from shared.models.operation import ExcelSourceFormat, FileSource, OperationConfig, SourceFormat
from shared.models.profiling import (
    BooleanColumnProfile,
    ColumnProfileStats,
    CurrencyColumnProfile,
    DateColumnProfile,
    NumericColumnProfile,
    ProfilingOutput,
)
from shared.models.source import SourceRef
from shared.storage.s3 import build_duckdb_s3_url, download_s3_temp, s3_ref
from shared.utils.column import build_position_to_name

NUMERIC_MISMATCH_THRESHOLD = 0.60


def _cleanup_temp_file(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)


def run_profiling(
    source: SourceRef,
    *,
    source_checksum: str,
    source_format: SourceFormat,
    column_config: dict[str, ColumnConfig],
    operation_config: OperationConfig,
) -> ProfilingOutput:
    """Run the full-dataset profiling phase using confirmed config."""
    cleanup_path: Path | None = None
    ingestion_type: FileSource = "local"
    if source.source_type == "s3" and isinstance(source_format, ExcelSourceFormat):
        cleanup_path = download_s3_temp(s3_ref(source.source_file))
        ingestion_url = str(cleanup_path)
    elif source.source_type == "s3":
        ingestion_url = build_duckdb_s3_url(s3_ref(source.source_file))
        ingestion_type = "s3"
    else:
        ingestion_url = source.source_file

    try:
        with DuckDBManager() as conn:
            run_ingestion(
                IngestionRequest(
                    conn=conn,
                    source_url=ingestion_url,
                    source_type=ingestion_type,
                    source_format=source_format,
                    table_name="raw_input",
                )
            )

            HeaderCanonicalizationStage().execute(conn)
            canonical_columns = read_columns(conn, "raw_input")
            position_to_name = build_position_to_name(canonical_columns)

            row_count, empty_row_count = compute_global_stats(
                conn,
                table_name="raw_input",
                null_tokens=operation_config.null_tokens,
            )
            _, null_stats = compute_null_stats(
                conn,
                table_name="raw_input",
                position_to_name=position_to_name,
                null_tokens=operation_config.null_tokens,
            )

            issues = []
            column_stats: dict[str, ColumnProfileStats] = {}
            currency_ratios: list[float] = []
            total_non_nullish_cells = 0

            for pos, column_name in position_to_name.items():
                config = column_config.get(pos)
                if config is None:
                    continue

                counts = null_stats[pos]
                total_non_nullish_cells += counts.non_nullish_count
                null_ratio = 0.0 if row_count <= 0 else (counts.null_count / row_count)
                nullish_ratio = 0.0 if row_count <= 0 else (counts.nullish_count / row_count)

                type_profile: (
                    CurrencyColumnProfile
                    | NumericColumnProfile
                    | DateColumnProfile
                    | BooleanColumnProfile
                    | None
                ) = None

                raw_col = f"TRIM(CAST({quote_identifier(column_name)} AS VARCHAR))"
                candidate = build_value_candidate_expr(raw_col, config)

                if isinstance(config, CurrencyColumnConfig | AccountingColumnConfig):
                    currency_profile = compute_currency_column_profile(
                        conn,
                        column_name=column_name,
                        null_tokens=operation_config.null_tokens,
                        counts=counts,
                    )
                    type_profile = currency_profile
                    currency_ratios.append(currency_profile.dominant_symbol_ratio)
                    if currency_profile.has_mixed_symbols:
                        issues.append(
                            build_mixed_currency_issue(
                                column_name=column_name,
                                symbols=sorted(currency_profile.symbol_distribution.keys()),
                                dominant_symbol=currency_profile.dominant_symbol,
                                dominant_symbol_ratio=currency_profile.dominant_symbol_ratio,
                            )
                        )

                if isinstance(
                    config,
                    IntegerColumnConfig
                    | DecimalColumnConfig
                    | CurrencyColumnConfig
                    | PercentageColumnConfig
                    | SignedColumnConfig
                    | AccountingColumnConfig,
                ):
                    numeric_profile = compute_numeric_column_profile(
                        conn,
                        column_name=column_name,
                        config=config,
                        null_tokens=operation_config.null_tokens,
                        counts=counts,
                        normalized_value_expr=candidate,
                    )
                    if type_profile is None:
                        type_profile = numeric_profile
                    if (
                        isinstance(
                            config,
                            DecimalColumnConfig
                            | CurrencyColumnConfig
                            | PercentageColumnConfig
                            | SignedColumnConfig
                            | AccountingColumnConfig,
                        )
                        and numeric_profile.separator_mismatch_detected
                        and numeric_profile.swapped_match_ratio >= NUMERIC_MISMATCH_THRESHOLD
                    ):
                        issues.append(
                            build_separator_mismatch_issue(
                                column_name=column_name,
                                decimal_separator=config.decimal_separator,
                                thousand_separator=config.thousand_separator,
                                numeric_threshold=NUMERIC_MISMATCH_THRESHOLD,
                                declared_decimal_ratio=numeric_profile.parse_match_ratio,
                                swapped_decimal_ratio=numeric_profile.swapped_match_ratio,
                            )
                        )

                elif isinstance(config, DateColumnConfig):
                    type_profile = compute_date_column_profile(
                        conn,
                        column_name=column_name,
                        date_format=config.date_format,
                        null_tokens=operation_config.null_tokens,
                        counts=counts,
                    )

                elif isinstance(config, BooleanColumnConfig):
                    type_profile = compute_boolean_column_profile(
                        conn,
                        column_name=column_name,
                        true_tokens=config.true_tokens,
                        false_tokens=config.false_tokens,
                        null_tokens=operation_config.null_tokens,
                        counts=counts,
                    )

                column_stats[pos] = ColumnProfileStats(
                    label=column_name,
                    column_type=column_config_type(config),
                    counts=counts,
                    null_ratio=null_ratio,
                    nullish_ratio=nullish_ratio,
                    type_profile=type_profile,
                )

            column_count = len(canonical_columns)
            total_cells = row_count * column_count
            completeness_ratio = (
                1.0 if total_cells <= 0 else (total_non_nullish_cells / total_cells)
            )
            pattern_consistency_ratio = (
                1.0 if not currency_ratios else (sum(currency_ratios) / len(currency_ratios))
            )
    finally:
        _cleanup_temp_file(cleanup_path)

    return ProfilingOutput(
        source_checksum=source_checksum,
        row_count=row_count,
        empty_row_count=empty_row_count,
        column_count=column_count,
        pattern_consistency_ratio=pattern_consistency_ratio,
        completeness_ratio=completeness_ratio,
        column_stats=column_stats,
        issues=issues,
    )
