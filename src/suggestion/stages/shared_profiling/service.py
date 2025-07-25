"""Shared one-pass column profiling used by multiple stages."""

from __future__ import annotations

from collections.abc import Mapping

from duckdb import DuckDBPyConnection

from normalize.core.column_positions import build_position_to_name
from normalize.core.numeric_formats import NumericFormat, resolve_numeric_formats_by_canonical
from normalize.core.token_policy import TokenPolicy
from suggestion.stages.shared_profiling.contracts import (
    DEFAULT_PROFILE_TABLE_NAME,
    ColumnProfile,
)
from suggestion.stages.shared_profiling.query_builders import (
    build_pass1_profile_query,
    build_pass2_currency_query,
)
from suggestion.stages.shared_profiling.sql_helpers import (
    read_data_columns,
    table_exists,
    validate_identifier,
)


def ensure_column_profiles(
    conn: DuckDBPyConnection,
    *,
    table_name: str = "raw_input",
    profile_table_name: str = DEFAULT_PROFILE_TABLE_NAME,
    token_policy: TokenPolicy,
    decimal_separator: str,
    thousand_separator: str,
    grouping_style: str,
    numeric_formats: Mapping[str, NumericFormat] | None,
    allow_leading_decimal_point: bool,
    currency_candidate_threshold: float,
) -> dict[str, ColumnProfile]:
    """
    Load cached column profiles when present; otherwise compute and store.

    Profiles are generated with an explicit `TokenPolicy` so downstream stages
    share the same null/boolean interpretation without re-scanning the table.
    """
    if table_exists(conn, profile_table_name):
        return read_column_profiles(conn, profile_table_name=profile_table_name)
    return compute_and_store_column_profiles(
        conn,
        table_name=table_name,
        profile_table_name=profile_table_name,
        token_policy=token_policy,
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
        grouping_style=grouping_style,
        numeric_formats=numeric_formats,
        allow_leading_decimal_point=allow_leading_decimal_point,
        currency_candidate_threshold=currency_candidate_threshold,
    )


def store_column_profiles(
    conn: DuckDBPyConnection,
    profiles: dict[str, ColumnProfile],
    *,
    profile_table_name: str = DEFAULT_PROFILE_TABLE_NAME,
) -> None:
    """Persist pre-computed column profiles into a DuckDB table."""
    validate_identifier(profile_table_name)
    conn.execute(
        f"""
        CREATE OR REPLACE TABLE {profile_table_name} (
            column_name VARCHAR,
            row_count BIGINT,
            non_empty_count BIGINT,
            bool_match_count BIGINT,
            int_match_count BIGINT,
            float_match_count BIGINT,
            swapped_float_match_count BIGINT,
            currency_match_count BIGINT,
            accounting_negative_match_count BIGINT,
            nullish_count BIGINT
        )
        """
    )
    if profiles:
        rows = [
            (
                p.column_name,
                p.row_count,
                p.non_empty_count,
                p.bool_match_count,
                p.int_match_count,
                p.float_match_count,
                p.swapped_float_match_count,
                p.currency_match_count,
                p.accounting_negative_match_count,
                p.nullish_count,
            )
            for p in profiles.values()
        ]
        conn.executemany(
            f"""
            INSERT INTO {profile_table_name}
                (column_name, row_count, non_empty_count, bool_match_count, int_match_count,
                 float_match_count, swapped_float_match_count, currency_match_count,
                 accounting_negative_match_count, nullish_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def compute_and_store_column_profiles(
    conn: DuckDBPyConnection,
    *,
    table_name: str = "raw_input",
    profile_table_name: str = DEFAULT_PROFILE_TABLE_NAME,
    token_policy: TokenPolicy,
    decimal_separator: str,
    thousand_separator: str,
    grouping_style: str,
    numeric_formats: Mapping[str, NumericFormat] | None,
    allow_leading_decimal_point: bool,
    currency_candidate_threshold: float,
) -> dict[str, ColumnProfile]:
    """
    Compute per-column counters in two passes and persist profile table.

    Pass 1 (all columns): null/bool/int/float counts — no currency expressions.
    Pass 2 (candidate columns only): currency expressions for columns whose
    float ratio from pass 1 is below `currency_candidate_threshold`. Columns
    at or above the threshold will be classified as decimal/integer by type
    inference regardless, so the currency scan would be wasted work.
    """
    validate_identifier(table_name)
    validate_identifier(profile_table_name)
    columns = read_data_columns(conn, table_name)
    position_to_canonical = build_position_to_name(columns)
    numeric_formats_by_column = resolve_numeric_formats_by_canonical(
        numeric_formats=numeric_formats,
        position_to_canonical=position_to_canonical,
    )

    if not columns:
        conn.execute(
            f"""
            CREATE OR REPLACE TABLE {profile_table_name} (
                column_name VARCHAR,
                row_count BIGINT,
                non_empty_count BIGINT,
                bool_match_count BIGINT,
                int_match_count BIGINT,
                float_match_count BIGINT,
                swapped_float_match_count BIGINT,
                currency_match_count BIGINT,
                accounting_negative_match_count BIGINT,
                nullish_count BIGINT
            )
            """
        )
        return {}

    # --- Pass 1: cheap counts for all columns ---
    pass1_query = build_pass1_profile_query(
        columns,
        table_name=table_name,
        token_policy=token_policy,
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
        grouping_style=grouping_style,
        numeric_formats_by_column=numeric_formats_by_column,
        allow_leading_decimal_point=allow_leading_decimal_point,
    )
    row = conn.execute(pass1_query).fetchone()
    if row is None:
        raise RuntimeError("pass1 profile query returned no rows")

    row_count = int(row[0])
    offset = 1
    # Columns per row in pass1: non_empty, bool, int, float, swapped, nullish = 6
    pass1_cols = 6
    pass1_data: dict[str, tuple[int, int, int, int, int, int]] = {}
    for column_name in columns:
        pass1_data[column_name] = (
            int(row[offset]),      # non_empty_count
            int(row[offset + 1]),  # bool_match_count
            int(row[offset + 2]),  # int_match_count
            int(row[offset + 3]),  # float_match_count
            int(row[offset + 4]),  # swapped_float_match_count
            int(row[offset + 5]),  # nullish_count
        )
        offset += pass1_cols

    # --- Determine currency candidates ---
    # Skip the currency pass for columns whose float ratio meets or exceeds the
    # threshold — those columns will be classified as decimal/integer by type
    # inference and need no currency analysis.
    currency_candidates = [
        col
        for col in columns
        if pass1_data[col][3] < pass1_data[col][0] * currency_candidate_threshold
    ]

    # --- Pass 2: currency expressions for candidates only ---
    currency_data: dict[str, tuple[int, int]] = {}  # col -> (currency_extra_match, acct_neg)
    if currency_candidates:
        pass2_query = build_pass2_currency_query(
            currency_candidates,
            table_name=table_name,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            grouping_style=grouping_style,
            numeric_formats_by_column=numeric_formats_by_column,
            allow_leading_decimal_point=allow_leading_decimal_point,
        )
        row2 = conn.execute(pass2_query).fetchone()
        if row2 is None:
            raise RuntimeError("pass2 currency query returned no rows")
        for i, col in enumerate(currency_candidates):
            currency_data[col] = (int(row2[i * 2]), int(row2[i * 2 + 1]))

    # --- Build profiles: merge pass1 + pass2 ---
    profiles: dict[str, ColumnProfile] = {}
    for column_name in columns:
        non_empty, bool_m, int_m, float_m, swapped_m, nullish_m = pass1_data[column_name]
        if column_name in currency_data:
            currency_extra_match_count, accounting_negative_match_count = currency_data[column_name]
            currency_match_count = min(non_empty, float_m + currency_extra_match_count)
        else:
            # Non-candidate: set currency_match_count = float_match_count.
            # Type inference picks decimal first (higher priority), so currency_ratio
            # will equal decimal_ratio -> infer_column_type won't select currency.
            currency_match_count = float_m
            accounting_negative_match_count = 0

        profiles[column_name] = ColumnProfile(
            column_name=column_name,
            row_count=row_count,
            non_empty_count=non_empty,
            bool_match_count=bool_m,
            int_match_count=int_m,
            float_match_count=float_m,
            swapped_float_match_count=swapped_m,
            currency_match_count=currency_match_count,
            accounting_negative_match_count=accounting_negative_match_count,
            nullish_count=nullish_m,
        )

    store_column_profiles(conn, profiles, profile_table_name=profile_table_name)
    return profiles


def read_column_profiles(
    conn: DuckDBPyConnection,
    *,
    profile_table_name: str = DEFAULT_PROFILE_TABLE_NAME,
) -> dict[str, ColumnProfile]:
    """Read previously computed profiles from profile table."""
    validate_identifier(profile_table_name)
    rows = conn.execute(
        f"""
        SELECT
            column_name,
            row_count,
            non_empty_count,
            bool_match_count,
            int_match_count,
            float_match_count,
            swapped_float_match_count,
            currency_match_count,
            accounting_negative_match_count,
            nullish_count
        FROM {profile_table_name}
        ORDER BY column_name
        """
    ).fetchall()

    profiles: dict[str, ColumnProfile] = {}
    for row in rows:
        profile = ColumnProfile(
            column_name=str(row[0]),
            row_count=int(row[1]),
            non_empty_count=int(row[2]),
            bool_match_count=int(row[3]),
            int_match_count=int(row[4]),
            float_match_count=int(row[5]),
            swapped_float_match_count=int(row[6]),
            currency_match_count=int(row[7]),
            accounting_negative_match_count=int(row[8]),
            nullish_count=int(row[9]),
        )
        profiles[profile.column_name] = profile
    return profiles
