"""Combined row + cell transform: compose SQL fragments, execute once."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from duckdb import DuckDBPyConnection

from normalize.core.sql_helpers import quote_identifier, validate_identifier


@dataclass(frozen=True)
class RowPlan:
    """SQL fragments produced by row normalization planning."""

    filter_predicate: str | None  # None = no filtering
    assign_indices: bool
    rows_before: int
    rows_dropped: int  # known from a cheap pre-check


@dataclass(frozen=True)
class CellPlan:
    """SQL fragments produced by cell normalization planning."""

    data_columns: tuple[str, ...]
    # (alias, expr) pairs for the pre-parse CTE — materialised once per row
    # so expensive sub-expressions (REGEXP_FULL_MATCH, TRY_CAST, TRY_STRPTIME)
    # are not re-evaluated for both the normalized value and the issue code.
    parse_cte_exprs: tuple[tuple[str, str], ...]
    # SELECT expressions for the base CTE:
    #   normalized column AS col, issue expr AS __issue__col
    column_select_exprs: tuple[str, ...]
    # Pairs for TO_JSON(STRUCT_PACK(...)) capturing pre-cast values
    raw_source_pairs: tuple[str, ...]
    # Pairs for TO_JSON(STRUCT_PACK(...)) capturing issue codes
    issue_pairs: tuple[str, ...]
    # Expression summing per-column error indicators
    row_error_expr: str
    # Final _raw_row expression (may be conditional on _parse_error_count)
    raw_row_expr: str
    # Final _parse_issues expression (may be conditional on _parse_error_count)
    parse_issues_expr: str
    emit_raw_row: bool
    full_raw_row: bool
    emit_parse_issues: bool


def compose_transform_sql(
    row_plan: RowPlan,
    cell_plan: CellPlan,
    *,
    table_name: str = "raw_input",
) -> str:
    """Compose a single CREATE OR REPLACE TABLE merging row filter + cell normalization.

    Uses two index strategies:
    - Fast path (no rows dropped): ``(rowid + 1)`` — avoids window function sort.
    - General path: ``ROW_NUMBER() OVER (ORDER BY rowid)`` with outer ORDER BY
      for deterministic gap-free indices after filtering.
    """
    validate_identifier(table_name)

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
            f"CREATE OR REPLACE TABLE {table_name} AS\n"
            f"WITH parsed AS (\n"
            f"    SELECT\n"
            f"        *,\n"
            f"        {',\n        '.join(parsed_select_extras)}\n"
            f"    FROM {table_name}\n"
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
        f"CREATE OR REPLACE TABLE {table_name} AS\n"
        f"WITH base AS (\n"
        f"    SELECT\n"
        f"        {',\n        '.join(base_parts)}\n"
        f"    FROM {table_name}\n"
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


def execute_combined_transform(
    conn: DuckDBPyConnection,
    row_plan: RowPlan,
    cell_plan: CellPlan,
    *,
    table_name: str = "raw_input",
) -> dict[str, object]:
    """Execute the composed transform and refresh quality precompute."""
    start = perf_counter()

    sql = compose_transform_sql(row_plan, cell_plan, table_name=table_name)
    conn.execute(sql)
    sql_seconds = perf_counter() - start

    rows_after = int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])

    t0 = perf_counter()
    _refresh_quality_profile(conn, table_name=table_name, data_columns=list(cell_plan.data_columns))
    precompute_seconds = perf_counter() - t0

    return {
        "duration_seconds": perf_counter() - start,
        "sql_seconds": sql_seconds,
        "precompute_seconds": precompute_seconds,
        "rows_before": row_plan.rows_before,
        "rows_after": rows_after,
        "rows_dropped": row_plan.rows_before - rows_after,
        "column_count": len(cell_plan.data_columns),
    }


def _refresh_quality_profile(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    data_columns: list[str],
) -> None:
    """Materialize lightweight per-column counters for the quality stage."""
    profile_table = "_quality_profile_raw_input"
    conn.execute(
        f"CREATE OR REPLACE TABLE {profile_table} ("
        "column_name VARCHAR, row_count BIGINT, "
        "nullish_count BIGINT, non_null_count BIGINT)"
    )
    if not data_columns:
        return

    agg_exprs: list[str] = ["COUNT(*) AS row_count"]
    for col in data_columns:
        q = quote_identifier(col)
        nullish_alias = quote_identifier(f"{col}__nullish")
        non_null_alias = quote_identifier(f"{col}__non_null")
        agg_exprs.append(
            f"SUM(CASE WHEN {q} IS NULL THEN 1 ELSE 0 END) AS {nullish_alias}"
        )
        agg_exprs.append(f"COUNT({q}) AS {non_null_alias}")

    row = conn.execute(f"SELECT {', '.join(agg_exprs)} FROM {table_name}").fetchone()
    if row is None:
        raise RuntimeError("quality precompute query returned no rows")

    row_count = int(row[0])
    inserts: list[tuple[str, int, int, int]] = []
    offset = 1
    for col in data_columns:
        nullish = int(row[offset])
        non_null = int(row[offset + 1])
        offset += 2
        inserts.append((col, row_count, nullish, non_null))

    conn.executemany(
        f"INSERT INTO {profile_table} "
        "(column_name, row_count, nullish_count, non_null_count) VALUES (?, ?, ?, ?)",
        inserts,
    )
