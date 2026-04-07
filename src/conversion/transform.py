"""SQL composition for the combined row+cell transform."""

from __future__ import annotations

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import quote_identifier

from conversion.constants import (
    CONDITIONAL_ERROR_COUNT_ALIAS,
    CONDITIONAL_RAW_JSON_ALIAS,
    PARSE_ERROR_COUNT_COLUMN,
    PARSE_ISSUES_COLUMN,
    RAW_ROW_COLUMN,
    ROW_INDEX_COLUMN,
    ROWID_PASSTHROUGH_ALIAS,
)
from conversion.models import CellPlan, RowPlan


def _compose_cte(
    name: str,
    select_parts: list[str],
    source: str,
    *clauses: str,
) -> str:
    select_sql = ",\n        ".join(select_parts)
    lines = [
        f"{name} AS (",
        "    SELECT",
        f"        {select_sql}",
        f"    FROM {source}",
    ]
    lines.extend(f"    {clause}" for clause in clauses if clause)
    lines.append(")")
    return "\n".join(lines)


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

    use_parse_cte = bool(cell_plan.parse_cte_exprs)

    # WHERE clause for empty row filtering
    filter_clause = ""
    if row_plan.filter_predicate and row_plan.rows_dropped > 0:
        filter_clause = f"WHERE {row_plan.filter_predicate}"

    # When a parse CTE is injected, rowid is only accessible on the base table.
    # Pass it through as __rowid so base can use it for index expressions.
    rowid_alias = ROWID_PASSTHROUGH_ALIAS
    rowid_ref = rowid_alias if use_parse_cte else "rowid"

    # Base CTE: filter + type cast + issue detection + indices + raw json
    base_parts: list[str] = list(cell_plan.column_select_exprs)
    outer_order = ""
    if row_plan.assign_indices:
        if row_plan.rows_dropped > 0:
            base_parts.append(
                f"(ROW_NUMBER() OVER (ORDER BY {rowid_ref}))::BIGINT AS {ROW_INDEX_COLUMN}"
            )
            # Outer ORDER BY rowid helps DuckDB optimize the window function sort.
            outer_order = f"ORDER BY {rowid_ref}"
        else:
            base_parts.append(f"({rowid_ref} + 1)::BIGINT AS {ROW_INDEX_COLUMN}")

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
        base_parts.append(f"({cell_plan.row_error_expr}) AS {CONDITIONAL_ERROR_COUNT_ALIAS}")
        base_parts.append(
            f"CASE WHEN {CONDITIONAL_ERROR_COUNT_ALIAS} > 0 "
            f"THEN {struct_json_expr} ELSE NULL END AS {CONDITIONAL_RAW_JSON_ALIAS}"
        )
    elif cell_plan.emit_raw_row and cell_plan.raw_source_pairs:
        base_parts.append(f"{struct_json_expr} AS {CONDITIONAL_RAW_JSON_ALIAS}")

    # Final projection
    projected: list[str] = [quote_identifier(col) for col in cell_plan.data_columns]
    if row_plan.assign_indices:
        projected.append(ROW_INDEX_COLUMN)

    # Error count expression — reuse __error_cnt when available
    if use_conditional_json:
        error_count_sql = f"{CONDITIONAL_ERROR_COUNT_ALIAS}::INTEGER"
        # __raw_json is already conditional from the base CTE
        raw_row_sql = CONDITIONAL_RAW_JSON_ALIAS
        # _parse_issues also conditional on __error_cnt
        if cell_plan.emit_parse_issues and cell_plan.issue_pairs:
            parse_issues_sql = (
                f"CASE WHEN {CONDITIONAL_ERROR_COUNT_ALIAS} > 0 "
                f"THEN TO_JSON(STRUCT_PACK({', '.join(cell_plan.issue_pairs)})) "
                "ELSE NULL END"
            )
        else:
            parse_issues_sql = "NULL::VARCHAR"
    else:
        error_count_sql = f"({cell_plan.row_error_expr})::INTEGER"
        raw_row_sql = cell_plan.raw_row_expr
        parse_issues_sql = cell_plan.parse_issues_expr

    ctes: list[str] = []
    base_source = RAW_INPUT_TABLE_NAME
    base_filter_clause = filter_clause

    if use_parse_cte:
        # Parse CTE materialises expensive sub-expressions once; base reads from it.
        # rowid is passed through explicitly so index expressions can reference it.
        parsed_select_extras = [
            f"{expr} AS {alias}" for alias, expr in cell_plan.parse_cte_exprs
        ]
        if row_plan.assign_indices:
            parsed_select_extras.insert(0, f"rowid AS {rowid_alias}")
        ctes.append(
            _compose_cte(
                "parsed",
                ["*", *parsed_select_extras],
                RAW_INPUT_TABLE_NAME,
                filter_clause,
            )
        )
        base_source = "parsed"
        base_filter_clause = ""

    ctes.append(
        _compose_cte(
            "base",
            base_parts,
            base_source,
            base_filter_clause,
            outer_order,
        )
    )
    with_sql = ",\n".join(ctes)

    return (
        f"CREATE OR REPLACE TABLE {RAW_INPUT_TABLE_NAME} AS\n"
        f"WITH {with_sql}\n"
        f"SELECT\n"
        f"    {', '.join(projected)},\n"
        f"    {error_count_sql} AS {PARSE_ERROR_COUNT_COLUMN},\n"
        f"    {raw_row_sql} AS {RAW_ROW_COLUMN},\n"
        f"    {parse_issues_sql} AS {PARSE_ISSUES_COLUMN}\n"
        "FROM base"
    )
