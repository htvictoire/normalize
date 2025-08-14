"""Constants shared across artifact materialization submodules."""

AUDIT_OUTPUT_COLUMNS = ("_row_index", "_global_row_index", "_raw_row", "_parse_issues")
AUDIT_EXCLUDED_FROM_DATA = {
    "_row_index",
    "_global_row_index",
    "_raw_row",
    "_parse_issues",
    "_parse_error_count",
}
