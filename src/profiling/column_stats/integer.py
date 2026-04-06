"""Integer profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import execute_scalar, nullish_predicate, quote_identifier, quote_string
from shared.models.column import IntegerColumnConfig
from shared.models.profiling import ColumnCounts, IntegerColumnProfile
from shared.parsing.numeric import integer_pattern_regex


def compute_integer_column_profile(
    conn: DuckDBPyConnection,
    column_name: str,
    config: IntegerColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> IntegerColumnProfile:
    """Count values that match the declared integer format."""
    quoted = quote_identifier(column_name)
    nullish = nullish_predicate(quoted, null_tokens)
    non_nullish = counts.non_nullish_count

    pattern = integer_pattern_regex(
        thousand_separator=config.thousand_separator,
        grouping_style=config.grouping_style,
    )
    parse_match_count = execute_scalar(
        conn,
        f"SELECT COUNT(*) FROM {RAW_INPUT_TABLE_NAME} WHERE NOT ({nullish}) "
        f"AND REGEXP_FULL_MATCH({normalized_value_expr}, {quote_string(pattern)})",
    )
    parse_match_ratio = 1.0 if non_nullish <= 0 else (parse_match_count / non_nullish)
    return IntegerColumnProfile(
        parse_match_count=parse_match_count,
        parse_match_ratio=parse_match_ratio,
    )
