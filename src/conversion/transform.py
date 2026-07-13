"""SQL composition for the combined row+cell transform."""

from __future__ import annotations

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import quote_identifier

from conversion.cells.naming import issue_alias
from conversion.constants import (
    CONDITIONAL_ERROR_COUNT_ALIAS,
    CONDITIONAL_RAW_JSON_ALIAS,
    PARSE_ERROR_COUNT_COLUMN,
    PARSE_ISSUES_COLUMN,
    PARSE_ISSUES_JSON_ALIAS,
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


def _build_row_error_expr(data_columns: tuple[str, ...]) -> str:
    terms = [
        f"CASE WHEN {quote_identifier(issue_alias(column_name))} IS NULL THEN 0 ELSE 1 END"
        for column_name in data_columns
    ]
    return "0" if not terms else " + ".join(terms)


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
    row_error_expr = _build_row_error_expr(cell_plan.data_columns)
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

    # Error count is materialised first (as a lateral column alias) so the issue
    # JSON below is only serialized for rows that actually failed. Clean rows
    # never pay for TO_JSON(STRUCT_PACK(...)) — worth ~10s on 10M clean rows.
    base_parts.append(f"({row_error_expr}) AS {CONDITIONAL_ERROR_COUNT_ALIAS}")

    # _parse_issues is unconditional: every failing cell records its issue code
    # and its original text. json_merge_patch drops the null keys, so the object
    # carries only the cells that failed, not one entry per column.
    if cell_plan.issue_pairs:
        base_parts.append(
            f"CASE WHEN {CONDITIONAL_ERROR_COUNT_ALIAS} > 0 "
            f"THEN json_merge_patch('{{}}', "
            f"TO_JSON(STRUCT_PACK({', '.join(cell_plan.issue_pairs)}))) "
            f"ELSE NULL END AS {PARSE_ISSUES_JSON_ALIAS}"
        )
        parse_issues_sql = PARSE_ISSUES_JSON_ALIAS
    else:
        parse_issues_sql = "NULL::VARCHAR"

    # _raw_row is the opt-in lineage column: originals for *every* cell, including
    # the ones that parsed. Failing cells already carry their original in
    # _parse_issues, so this is only needed for full-source provenance.
    if cell_plan.full_raw_row and cell_plan.raw_source_pairs:
        base_parts.append(
            f"TO_JSON(STRUCT_PACK({', '.join(cell_plan.raw_source_pairs)})) "
            f"AS {CONDITIONAL_RAW_JSON_ALIAS}"
        )
        raw_row_sql = CONDITIONAL_RAW_JSON_ALIAS
    else:
        raw_row_sql = "NULL::VARCHAR"

    # Final projection
    projected: list[str] = [quote_identifier(col) for col in cell_plan.data_columns]
    if row_plan.assign_indices:
        projected.append(ROW_INDEX_COLUMN)

    error_count_sql = f"{CONDITIONAL_ERROR_COUNT_ALIAS}::INTEGER"

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
