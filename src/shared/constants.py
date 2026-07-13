"""Shared cross-package constants."""

from __future__ import annotations

RAW_INPUT_TABLE_NAME = "raw_input"
EXCEL_SERIAL_DATE_EPOCH_SQL = "DATE '1899-12-30'"

# DuckDB backs a DECIMAL with an int64 up to 18 digits of precision and an int128 beyond
# it. 38 is the maximum, for DuckDB and for Parquet alike.
#
# The boundary is a cliff, not a slope: parsing a value into an int128 DECIMAL costs
# roughly 500x what an int64 one costs (7ms vs 5.4s per million rows). A column is
# therefore given the int64 precision whenever its digits fit inside it.
DECIMAL_INT64_MAX_PRECISION = 18
DECIMAL_MAX_PRECISION = 38
