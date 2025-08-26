"""Numeric profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from conversion.stages.cell_normalization.transforms.numeric import (
    decimal_pattern_regex,
    integer_pattern_regex,
)
from shared.db.sql import nullish_predicate, quote_identifier, quote_string
from shared.models.column import CurrencyColumnConfig, DecimalColumnConfig, IntegerColumnConfig
from shared.models.profiling import ColumnCounts, NumericColumnProfile


def compute_numeric_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    config: DecimalColumnConfig | IntegerColumnConfig | CurrencyColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
) -> NumericColumnProfile:
    """Count matches for the declared format; detect separator swaps where applicable."""
    quoted = quote_identifier(column_name)
    raw_value = f"TRIM(CAST({quoted} AS VARCHAR))"
    nullish = nullish_predicate(quoted, null_tokens)
    non_nullish = counts.non_nullish_count

    if isinstance(config, IntegerColumnConfig):
        pattern = integer_pattern_regex(
            thousand_separator=config.thousand_separator,
            grouping_style=config.grouping_style,
        )
        row = conn.execute(
            f"SELECT COUNT(*) FROM raw_input WHERE NOT ({nullish}) "
            f"AND REGEXP_FULL_MATCH({raw_value}, {quote_string(pattern)})"
        ).fetchone()
        if row is None:
            raise RuntimeError("integer pattern count query returned no rows")
        parse_match_count = int(row[0])
        parse_match_ratio = 1.0 if non_nullish <= 0 else (parse_match_count / non_nullish)
        return NumericColumnProfile(
            parse_match_count=parse_match_count,
            parse_match_ratio=parse_match_ratio,
            swapped_match_count=0,
            swapped_match_ratio=0.0,
            separator_mismatch_detected=False,
        )

    declared_pattern = decimal_pattern_regex(
        decimal_separator=config.decimal_separator,
        thousand_separator=config.thousand_separator,
        grouping_style=config.grouping_style,
        allow_leading_decimal_point=getattr(config, "allow_leading_decimal_point", False),
    )
    swapped_pattern = decimal_pattern_regex(
        decimal_separator=config.thousand_separator,
        thousand_separator=config.decimal_separator,
        grouping_style=config.grouping_style,
        allow_leading_decimal_point=getattr(config, "allow_leading_decimal_point", False),
    )

    declared_row = conn.execute(
        f"SELECT COUNT(*) FROM raw_input WHERE NOT ({nullish}) "
        f"AND REGEXP_FULL_MATCH({raw_value}, {quote_string(declared_pattern)})"
    ).fetchone()
    if declared_row is None:
        raise RuntimeError("declared pattern count query returned no rows")
    parse_match_count = int(declared_row[0])

    swapped_row = conn.execute(
        f"SELECT COUNT(*) FROM raw_input WHERE NOT ({nullish}) "
        f"AND REGEXP_FULL_MATCH({raw_value}, {quote_string(swapped_pattern)})"
    ).fetchone()
    if swapped_row is None:
        raise RuntimeError("swapped pattern count query returned no rows")
    swapped_match_count = int(swapped_row[0])

    parse_match_ratio = 1.0 if non_nullish <= 0 else (parse_match_count / non_nullish)
    swapped_match_ratio = 1.0 if non_nullish <= 0 else (swapped_match_count / non_nullish)

    return NumericColumnProfile(
        parse_match_count=parse_match_count,
        parse_match_ratio=parse_match_ratio,
        swapped_match_count=swapped_match_count,
        swapped_match_ratio=swapped_match_ratio,
        separator_mismatch_detected=swapped_match_count > parse_match_count,
    )
