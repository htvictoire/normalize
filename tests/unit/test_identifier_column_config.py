from __future__ import annotations

import json

from pydantic import TypeAdapter

from shared.db.duckdb import DuckDBManager
from shared.models.column import ColumnConfig, IdentifierColumnConfig, IntegerColumnConfig
from shared.models.operation import DecisionThresholds, OperationConfig

from suggestion.rule_based.inference import infer_column, infer_column_type

from profiling.counts import compute_profiling_stats
from profiling.profiles import compute_profile_results

from conversion.pipeline import run_conversion


def _operation_config() -> OperationConfig:
    return OperationConfig(
        null_tokens=("", "null"),
        assign_indices=True,
        drop_empty_rows=False,
        emit_raw_row=True,
        full_raw_row=False,
        emit_parse_issues=True,
        include_unique_ratio=True,
        include_per_column_parse_error_counts=False,
        approximate_unique=False,
        trace_mode="sparse",
        decision_thresholds=DecisionThresholds(ready=95.0, warning=85.0),
    )


def test_identifier_config_round_trips_through_column_config_union() -> None:
    adapter = TypeAdapter(ColumnConfig)

    assert adapter.validate_python(
        {"type": "identifier", "identifier_kind": "primary"}
    ) == IdentifierColumnConfig(identifier_kind="primary")


def test_rule_based_identifier_inference_uses_header_and_sample_uniqueness() -> None:
    inference = infer_column(
        ["001", "002", "003", "004"],
        extended_type_detection=False,
        column_name="order_id",
    )

    assert inference.config == IdentifierColumnConfig(identifier_kind="foreign")
    assert inference.confidence >= 0.85


def test_rule_based_identifier_inference_does_not_capture_plain_numeric_columns() -> None:
    assert infer_column_type(
        ["001", "002", "003", "004"],
        extended_type_detection=False,
        column_name="amount",
    ) == IntegerColumnConfig(thousand_separator="", grouping_style="western")


def test_identifier_conversion_preserves_leading_zeroes_and_profiles_duplicates() -> None:
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (order_id VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                (' 001 '),
                ('002'),
                ('002')
            """
        )

        config = {"A": IdentifierColumnConfig(identifier_kind="primary")}
        run_conversion(
            conn,
            confirmed_column_config=config,
            operation_config=_operation_config(),
        )

        rows = conn.execute(
            """
            SELECT order_id, _parse_error_count, _parse_issues
            FROM raw_input
            ORDER BY _row_index
            """
        ).fetchall()

    assert rows == [("001", 0, None), ("002", 0, None), ("002", 0, None)]


def test_identifier_profiling_reports_duplicate_values() -> None:
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (order_id VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('001'),
                ('002'),
                ('002')
            """
        )
        counts = compute_profiling_stats(conn, ["order_id"], null_tokens=("", "null"))
        profile_results = compute_profile_results(
            conn,
            columns=["order_id"],
            column_config={"order_id": IdentifierColumnConfig(identifier_kind="primary")},
            null_tokens=("", "null"),
            counts_by_name=counts.column_counts,
            row_count=counts.row_count,
        )

    profile = profile_results.column_stats["order_id"].type_profile
    assert profile.profile_type == "identifier"
    assert profile.distinct_count == 2
    assert profile.duplicate_count == 1
    assert [issue.code for issue in profile_results.issues] == ["IDENTIFIER_DUPLICATES"]
    assert json.dumps(profile_results.issues[0].evidence) == (
        '{"duplicate_count": 1, "distinct_count": 2, "uniqueness_ratio": '
        "0.6666666666666666}"
    )
