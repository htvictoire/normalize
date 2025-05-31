"""Header canonicalization stage."""

from __future__ import annotations

import re
from time import perf_counter

from duckdb import DuckDBPyConnection

from normalize.core.sql_helpers import (
    quote_identifier,
    read_columns,
    validate_identifier,
)
from normalize.stages.base import Stage


class HeaderCanonicalizationStage(Stage):
    """
    Canonicalize `raw_input` column names and apply deterministic uniqueness.

    Rules:
    1. trim
    2. lowercase
    3. replace non-alphanumeric spans with `_`
    4. strip leading/trailing `_`
    5. fallback to `column` when empty
    6. enforce uniqueness with `_2`, `_3`, ...
    """

    def execute(self, conn: DuckDBPyConnection, table_name: str = "raw_input") -> dict[str, str]:
        start_time = perf_counter()
        validate_identifier(table_name)
        columns = read_columns(conn, table_name)
        mapping = canonicalize_headers(columns)
        _apply_column_renames(conn, table_name, mapping)

        renamed_count = sum(1 for raw, canonical in mapping.items() if raw != canonical)
        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "column_count": len(columns),
            "renamed_count": renamed_count,
        }
        return mapping


def canonicalize_headers(columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used_counts: dict[str, int] = {}

    for raw in columns:
        base = _canonical_base(raw)
        next_count = used_counts.get(base, 0) + 1
        used_counts[base] = next_count
        canonical = base if next_count == 1 else f"{base}_{next_count}"
        mapping[raw] = canonical
    return mapping


def _canonical_base(header: str) -> str:
    value = header.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    if value == "":
        return "column"
    return value


def _apply_column_renames(
    conn: DuckDBPyConnection, table_name: str, mapping: dict[str, str]
) -> None:
    validate_identifier(table_name)
    rename_pairs = [(raw, canonical) for raw, canonical in mapping.items() if raw != canonical]
    if not rename_pairs:
        return

    # Batch metadata-only renames in one transaction to reduce statement
    # overhead while keeping behavior row-count independent.
    conn.execute("BEGIN TRANSACTION")
    try:
        for raw, canonical in rename_pairs:
            conn.execute(
                f"ALTER TABLE {table_name} RENAME COLUMN "
                f"{quote_identifier(raw)} TO {quote_identifier(canonical)}"
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
