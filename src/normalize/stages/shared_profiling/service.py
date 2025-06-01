"""Shared one-pass column profiling used by multiple stages."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from normalize.core.token_policy import TokenPolicy
from normalize.stages.shared_profiling.contracts import (
    DEFAULT_PROFILE_TABLE_NAME,
    ColumnProfile,
)
from normalize.stages.shared_profiling.query_builder import build_profile_query
from normalize.stages.shared_profiling.sql_helpers import (
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
                p.nullish_count,
            )
            for p in profiles.values()
        ]
        conn.executemany(
            f"""
            INSERT INTO {profile_table_name}
                (column_name, row_count, non_empty_count, bool_match_count, int_match_count,
                 float_match_count, nullish_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def compute_and_store_column_profiles(
    conn: DuckDBPyConnection,
    *,
    table_name: str = "raw_input",
    profile_table_name: str = DEFAULT_PROFILE_TABLE_NAME,
    token_policy: TokenPolicy,
) -> dict[str, ColumnProfile]:
    """
    Compute per-column counters in one aggregate scan and persist profile table.
    """
    validate_identifier(table_name)
    validate_identifier(profile_table_name)
    columns = read_data_columns(conn, table_name)

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
                nullish_count BIGINT
            )
            """
        )
        return {}

    query = build_profile_query(columns, table_name=table_name, token_policy=token_policy)
    row = conn.execute(query).fetchone()
    if row is None:
        raise RuntimeError("profile query returned no rows")

    row_count = int(row[0])
    offset = 1
    profiles: dict[str, ColumnProfile] = {}

    for column_name in columns:
        non_empty_count = int(row[offset])
        bool_match_count = int(row[offset + 1])
        int_match_count = int(row[offset + 2])
        float_match_count = int(row[offset + 3])
        nullish_count = int(row[offset + 4])
        offset += 5

        profiles[column_name] = ColumnProfile(
            column_name=column_name,
            row_count=row_count,
            non_empty_count=non_empty_count,
            bool_match_count=bool_match_count,
            int_match_count=int_match_count,
            float_match_count=float_match_count,
            nullish_count=nullish_count,
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
            nullish_count=int(row[6]),
        )
        profiles[profile.column_name] = profile
    return profiles
