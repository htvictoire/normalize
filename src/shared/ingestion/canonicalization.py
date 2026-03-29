"""Header canonicalization stage."""

from __future__ import annotations

import re

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import quote_identifier, read_columns


class HeaderCanonicalizationStage:
    """
    Canonicalize ingested column names and apply deterministic uniqueness.

    Rules:
    1. trim
    2. lowercase
    3. replace non-alphanumeric spans with `_`
    4. strip leading/trailing `_`
    5. fallback to `column` when empty
    6. enforce uniqueness with `_2`, `_3`, ...
    """

    def execute(self, conn: DuckDBPyConnection) -> dict[str, str]:
        columns = read_columns(conn)
        canonical_columns = canonicalize_header_sequence(columns)
        mapping = _build_raw_to_canonical_mapping(columns, canonical_columns)
        _apply_column_renames(conn, columns, canonical_columns)
        return mapping


def canonicalize_headers(columns: list[str]) -> dict[str, str]:
    canonical_columns = canonicalize_header_sequence(columns)
    return _build_raw_to_canonical_mapping(columns, canonical_columns)


def canonicalize_header_sequence(columns: list[str]) -> list[str]:
    canonical_columns: list[str] = []
    used_counts: dict[str, int] = {}

    for raw in columns:
        base = _canonical_base(raw)
        next_count = used_counts.get(base, 0) + 1
        used_counts[base] = next_count
        canonical = base if next_count == 1 else f"{base}_{next_count}"
        canonical_columns.append(canonical)
    return canonical_columns


def _canonical_base(header: str) -> str:
    value = header.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    if not value:
        return "column"
    return value


def _apply_column_renames(
    conn: DuckDBPyConnection,
    raw_columns: list[str],
    canonical_columns: list[str],
) -> None:
    rename_pairs = [
        (raw, canonical)
        for raw, canonical in zip(raw_columns, canonical_columns, strict=False)
        if raw != canonical
    ]
    if not rename_pairs:
        return

    conn.execute("BEGIN TRANSACTION")
    try:
        for raw, canonical in rename_pairs:
            conn.execute(
                f"ALTER TABLE {RAW_INPUT_TABLE_NAME} RENAME COLUMN "
                f"{quote_identifier(raw)} TO {quote_identifier(canonical)}"
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _build_raw_to_canonical_mapping(
    raw_columns: list[str], canonical_columns: list[str]
) -> dict[str, str]:
    if len(raw_columns) != len(canonical_columns):
        raise ValueError("raw_columns and canonical_columns must be same length")
    duplicate_counts: dict[str, int] = {}
    duplicate_total: dict[str, int] = {}
    for raw in raw_columns:
        duplicate_total[raw] = duplicate_total.get(raw, 0) + 1

    mapping: dict[str, str] = {}
    for raw, canonical in zip(raw_columns, canonical_columns, strict=False):
        duplicate_counts[raw] = duplicate_counts.get(raw, 0) + 1
        ordinal = duplicate_counts[raw]
        key = raw if duplicate_total[raw] <= 1 else f"{raw}#{ordinal}"
        mapping[key] = canonical
    return mapping
