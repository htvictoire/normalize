"""Profile-phase pipeline over full dataset."""

from __future__ import annotations

from pathlib import Path
from profile.issues import build_mixed_currency_issue, build_separator_mismatch_issue
from profile.models import (
    BooleanColumnProfile,
    ColumnProfileStats,
    CurrencyColumnProfile,
    DateColumnProfile,
    NumericColumnProfile,
    ProfileOutput,
)
from profile.stats import (
    compute_boolean_column_profile,
    compute_currency_column_profile,
    compute_date_column_profile,
    compute_global_stats,
    compute_null_stats,
    compute_numeric_column_profile,
)

from normalize.stages.header_canonicalization import HeaderCanonicalizationStage
from shared.db.duckdb import DuckDBManager
from shared.db.sql import read_columns
from shared.ingestion import HeaderMode, IngestionRequest, run_ingestion
from shared.ingestion.checksum import sha256_stream
from shared.models.column import (
    BooleanColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
    column_config_type,
)
from shared.models.operation import OperationConfig, SourceFormatConfig
from shared.utils.column_positions import build_position_to_name

NUMERIC_MISMATCH_THRESHOLD = 0.60


def run_profile(
    file_path: str | Path,
    *,
    source_format: SourceFormatConfig,
    column_config: dict[str, ColumnConfig],
    operation_config: OperationConfig,
) -> ProfileOutput:
    """Run full-dataset profile phase using confirmed config."""
    source_file = Path(file_path)
    source_checksum = sha256_stream(source_file)

    with DuckDBManager() as conn:
        run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=source_file,
                table_name="raw_input",
                header_mode=HeaderMode(source_format.header_mode),
                header_row_index=source_format.header_row_index,
                encoding=source_format.encoding,
                delimiter=source_format.delimiter,
            )
        )

        HeaderCanonicalizationStage().execute(conn)
        canonical_columns = read_columns(conn, "raw_input")
        position_to_name = build_position_to_name(canonical_columns)
        resolved_column_config = {
            position_to_name[position_key]: spec for position_key, spec in column_config.items()
        }

        row_count, empty_row_count = compute_global_stats(
            conn,
            table_name="raw_input",
            null_tokens=operation_config.null_tokens,
        )
        null_stats = compute_null_stats(
            conn,
            table_name="raw_input",
            column_names=canonical_columns,
            null_tokens=operation_config.null_tokens,
        )

        issues = []
        column_stats: dict[str, ColumnProfileStats] = {}
        currency_ratios: list[float] = []
        total_non_null_cells = 0

        for column_name in canonical_columns:
            config = resolved_column_config.get(column_name)
            if config is None:
                continue

            null_count, non_null_count = null_stats[column_name]
            total_non_null_cells += non_null_count
            null_ratio = 0.0 if row_count <= 0 else (null_count / row_count)
            type_profile: (
                CurrencyColumnProfile
                | NumericColumnProfile
                | DateColumnProfile
                | BooleanColumnProfile
                | None
            ) = None

            if isinstance(config, CurrencyColumnConfig):
                currency_profile = compute_currency_column_profile(
                    conn,
                    column_name=column_name,
                    null_tokens=operation_config.null_tokens,
                    non_null_count=non_null_count,
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

                numeric_profile = compute_numeric_column_profile(
                    conn,
                    column_name=column_name,
                    config=config,
                    null_tokens=operation_config.null_tokens,
                    non_null_count=non_null_count,
                )
                if (
                    numeric_profile.separator_mismatch_detected
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

            elif isinstance(config, (DecimalColumnConfig, IntegerColumnConfig)):
                numeric_profile = compute_numeric_column_profile(
                    conn,
                    column_name=column_name,
                    config=config,
                    null_tokens=operation_config.null_tokens,
                    non_null_count=non_null_count,
                )
                type_profile = numeric_profile
                if (
                    numeric_profile.separator_mismatch_detected
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
                    non_null_count=non_null_count,
                )

            elif isinstance(config, BooleanColumnConfig):
                type_profile = compute_boolean_column_profile(
                    conn,
                    column_name=column_name,
                    true_tokens=operation_config.boolean_true_tokens,
                    false_tokens=operation_config.boolean_false_tokens,
                    null_tokens=operation_config.null_tokens,
                    non_null_count=non_null_count,
                )

            column_stats[column_name] = ColumnProfileStats(
                column_type=column_config_type(config),
                null_count=null_count,
                non_null_count=non_null_count,
                null_ratio=null_ratio,
                type_profile=type_profile,
            )

        column_count = len(canonical_columns)
        total_cells = row_count * column_count
        completeness_ratio = 1.0 if total_cells <= 0 else (total_non_null_cells / total_cells)
        pattern_consistency_ratio = (
            1.0 if not currency_ratios else (sum(currency_ratios) / len(currency_ratios))
        )

    return ProfileOutput(
        source_checksum=source_checksum,
        row_count=row_count,
        empty_row_count=empty_row_count,
        column_count=column_count,
        pattern_consistency_ratio=pattern_consistency_ratio,
        completeness_ratio=completeness_ratio,
        column_stats=column_stats,
        issues=issues,
    )
