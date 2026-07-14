"""Date expression builder."""

from __future__ import annotations

from shared.db.sql import quote_identifier
from shared.parsing.temporal import date_parse_expr, datetime_parse_expr, time_parse_expr

from conversion.cells.exprs.column_exprs import ColumnExprs
from conversion.cells.naming import parse_date_alias, parse_datetime_alias, parse_time_alias


def _build_temporal_exprs(
    alias: str,
    parse_expr: str,
    nullish_predicate: str,
    issue_label: str,
) -> ColumnExprs:
    normalized = f"CASE WHEN {nullish_predicate} THEN NULL ELSE {alias} END"
    issue = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {alias} IS NULL THEN '{issue_label}' "
        "ELSE NULL END"
    )
    return ColumnExprs(
        parse_cte_entries=((alias, parse_expr),),
        normalized_expr=normalized,
        issue_expr=issue,
    )


def build_date_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    day_first: bool,
    issue_label: str = "INVALID_DATE",
) -> ColumnExprs:
    """Build ColumnExprs for a date column."""
    date_alias = quote_identifier(parse_date_alias(column_name))
    date_expr = date_parse_expr(raw_value, day_first)
    return _build_temporal_exprs(date_alias, date_expr, nullish_predicate, issue_label)


def build_datetime_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    day_first: bool,
    issue_label: str = "INVALID_DATETIME",
) -> ColumnExprs:
    """Build ColumnExprs for a datetime/timestamp column."""
    datetime_alias = quote_identifier(parse_datetime_alias(column_name))
    datetime_expr = datetime_parse_expr(raw_value, day_first)
    return _build_temporal_exprs(
        datetime_alias,
        datetime_expr,
        nullish_predicate,
        issue_label,
    )


def build_time_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    issue_label: str = "INVALID_TIME",
) -> ColumnExprs:
    """Build ColumnExprs for a time-of-day column."""
    time_alias = quote_identifier(parse_time_alias(column_name))
    time_expr = time_parse_expr(raw_value)
    return _build_temporal_exprs(time_alias, time_expr, nullish_predicate, issue_label)
