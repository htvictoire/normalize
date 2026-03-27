"""SQL composition for the combined row+cell transform."""

from __future__ import annotations

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import quote_identifier, validate_identifier

from conversion.core.transform.models import CellPlan, RowPlan


def compose_transform_sql(
    row_plan: RowPlan,
    cell_plan: CellPlan,
) -> str:
    """Compose a single CREATE OR REPLACE TABLE merging row filter + cell normalization.

    Uses two index strategies:
    - Fast path (no rows dropped): ``(rowid + 1)`` — avoids window function sort.
    - General path: ``ROW_NUMBER() OVER (ORDER BY rowid)`` with outer ORDER BY
      for deterministic gap-free indices after filtering.
    """
    validate_identifier(RAW_INPUT_TABLE_NAME)

    needs_window = row_plan.assign_indices and row_plan.rows_dropped > 0
    needs_rowid_index = row_plan.assign_indices and row_plan.rows_dropped == 0
    use_parse_cte = bool(cell_plan.parse_cte_exprs)

    # WHERE clause for empty row filtering
    filter_clause = ""
    if row_plan.filter_predicate and row_plan.rows_dropped > 0:
        filter_clause = f"WHERE {row_plan.filter_predicate}"

    # When a parse CTE is injected, rowid is only accessible on the base table.
    # Pass it through as __rowid so base can use it for index expressions.
    rowid_alias = "__rowid"
    rowid_ref = rowid_alias if use_parse_cte else "rowid"

    # Base CTE: filter + type cast + issue detection + indices + raw json
    base_parts: list[str] = list(cell_plan.column_select_exprs)
    if needs_window:
        base_parts.append(
            f"(ROW_NUMBER() OVER (ORDER BY {rowid_ref}))::BIGINT AS _row_index"
        )
        base_parts.append(
            f"(ROW_NUMBER() OVER (ORDER BY {rowid_ref}))::BIGINT AS _global_row_index"
        )
    elif needs_rowid_index:
        base_parts.append(f"({rowid_ref} + 1)::BIGINT AS _row_index")
        base_parts.append(f"({rowid_ref} + 1)::BIGINT AS _global_row_index")

    # Conditional JSON optimization: when full_raw_row=False, compute __error_cnt
    # first (via lateral column alias) and only serialize JSON for rows with errors.
    # This avoids TO_JSON(STRUCT_PACK(...)) for every row — saves ~10s on 10M rows
    # when most rows have no parse errors.
    use_conditional_json = (
        cell_plan.emit_raw_row
        and not cell_plan.full_raw_row
        and cell_plan.raw_source_pairs
    )
    struct_json_expr = (
        f"TO_JSON(STRUCT_PACK({', '.join(cell_plan.raw_source_pairs)}))"
        if cell_plan.raw_source_pairs
        else "NULL::VARCHAR"
    )

    if use_conditional_json:
        # Error count as lateral alias — referenced by conditional __raw_json below
        base_parts.append(f"({cell_plan.row_error_expr}) AS __error_cnt")
        base_parts.append(
            f"CASE WHEN __error_cnt > 0 THEN {struct_json_expr} ELSE NULL END AS __raw_json"
        )
    elif cell_plan.emit_raw_row and cell_plan.raw_source_pairs:
        base_parts.append(f"{struct_json_expr} AS __raw_json")

    # Final projection
    projected: list[str] = [quote_identifier(col) for col in cell_plan.data_columns]
    if row_plan.assign_indices:
        projected.extend(["_row_index", "_global_row_index"])

    # Error count expression — reuse __error_cnt when available
    if use_conditional_json:
        error_count_sql = "__error_cnt::INTEGER"
        # __raw_json is already conditional from the base CTE
        raw_row_sql = "__raw_json"
        # _parse_issues also conditional on __error_cnt
        if cell_plan.emit_parse_issues and cell_plan.issue_pairs:
            parse_issues_sql = (
                "CASE WHEN __error_cnt > 0 "
                f"THEN TO_JSON(STRUCT_PACK({', '.join(cell_plan.issue_pairs)})) "
                "ELSE NULL END"
            )
        else:
            parse_issues_sql = "NULL::VARCHAR"
    else:
        error_count_sql = f"({cell_plan.row_error_expr})::INTEGER"
        raw_row_sql = cell_plan.raw_row_expr
        parse_issues_sql = cell_plan.parse_issues_expr

    # Outer ORDER BY rowid helps DuckDB optimize the window function sort
    outer_order = f"\nORDER BY {rowid_ref}" if needs_window else ""

    if use_parse_cte:
        # Parse CTE materialises expensive sub-expressions once; base reads from it.
        # rowid is passed through explicitly so index expressions can reference it.
        parse_intermediate_exprs = [
            f"{expr} AS {alias}" for alias, expr in cell_plan.parse_cte_exprs
        ]
        rowid_passthrough = f"rowid AS {rowid_alias}" if row_plan.assign_indices else ""
        parsed_select_extras = (
            [rowid_passthrough, *parse_intermediate_exprs]
            if rowid_passthrough
            else parse_intermediate_exprs
        )
        return (
            f"CREATE OR REPLACE TABLE {RAW_INPUT_TABLE_NAME} AS\n"
            f"WITH parsed AS (\n"
            f"    SELECT\n"
            f"        *,\n"
            f"        {',\n        '.join(parsed_select_extras)}\n"
            f"    FROM {RAW_INPUT_TABLE_NAME}\n"
            f"    {filter_clause}\n"
            f"),\n"
            f"base AS (\n"
            f"    SELECT\n"
            f"        {',\n        '.join(base_parts)}\n"
            f"    FROM parsed\n"
            f"    {outer_order}\n"
            f")\n"
            f"SELECT\n"
            f"    {', '.join(projected)},\n"
            f"    {error_count_sql} AS _parse_error_count,\n"
            f"    {raw_row_sql} AS _raw_row,\n"
            f"    {parse_issues_sql} AS _parse_issues\n"
            f"FROM base"
        )

    return (
        f"CREATE OR REPLACE TABLE {RAW_INPUT_TABLE_NAME} AS\n"
        f"WITH base AS (\n"
        f"    SELECT\n"
        f"        {',\n        '.join(base_parts)}\n"
        f"    FROM {RAW_INPUT_TABLE_NAME}\n"
        f"    {filter_clause}\n"
        f"    {outer_order}\n"
        f")\n"
        f"SELECT\n"
        f"    {', '.join(projected)},\n"
        f"    {error_count_sql} AS _parse_error_count,\n"
        f"    {raw_row_sql} AS _raw_row,\n"
        f"    {parse_issues_sql} AS _parse_issues\n"
        f"FROM base"
    )
