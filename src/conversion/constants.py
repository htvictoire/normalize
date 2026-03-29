"""Conversion-phase schema constants."""

from __future__ import annotations

# Audit columns appended by the conversion transform — excluded from data column lists.
AUDIT_COLUMNS: frozenset[str] = frozenset({
    "_row_index",
    "_global_row_index",
    "_raw_row",
    "_parse_issues",
    "_parse_error_count",
})

# Row index columns — only present when assign_indices=True.
AUDIT_INDEX_COLUMNS: tuple[str, ...] = ("_row_index", "_global_row_index")

# Record-level audit columns — always written by the transform (NULL when disabled).
AUDIT_RECORD_COLUMNS: tuple[str, ...] = ("_raw_row", "_parse_issues")

# Ordered parquet output subset (excludes _parse_error_count).
AUDIT_OUTPUT_COLUMNS: tuple[str, ...] = AUDIT_INDEX_COLUMNS + AUDIT_RECORD_COLUMNS
