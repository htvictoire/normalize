"""Conversion-phase schema constants."""

from __future__ import annotations

ROW_INDEX_COLUMN = "_row_index"
RAW_ROW_COLUMN = "_raw_row"
PARSE_ISSUES_COLUMN = "_parse_issues"
PARSE_ERROR_COUNT_COLUMN = "_parse_error_count"

ROWID_PASSTHROUGH_ALIAS = "__rowid"
CONDITIONAL_ERROR_COUNT_ALIAS = "__error_cnt"
CONDITIONAL_RAW_JSON_ALIAS = "__raw_json"
PARQUET_COPY_OPTIONS = "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"

# Audit columns appended by the conversion transform — excluded from data column lists.
AUDIT_COLUMNS: frozenset[str] = frozenset({
    ROW_INDEX_COLUMN,
    RAW_ROW_COLUMN,
    PARSE_ISSUES_COLUMN,
    PARSE_ERROR_COUNT_COLUMN,
})

# Row index columns — only present when assign_indices=True.
AUDIT_INDEX_COLUMNS: tuple[str, ...] = (ROW_INDEX_COLUMN,)

# Record-level audit columns — always written by the transform (NULL when disabled).
AUDIT_RECORD_COLUMNS: tuple[str, ...] = (RAW_ROW_COLUMN, PARSE_ISSUES_COLUMN)

# Ordered parquet output subset (excludes _parse_error_count).
AUDIT_OUTPUT_COLUMNS: tuple[str, ...] = AUDIT_INDEX_COLUMNS + AUDIT_RECORD_COLUMNS
