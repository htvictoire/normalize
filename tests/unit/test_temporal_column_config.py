import json

import pytest
from pydantic import TypeAdapter, ValidationError

from shared.db.duckdb import DuckDBManager
from shared.models.column import (
    ColumnConfig,
    DateTimeColumnConfig,
    TimeColumnConfig,
    column_config_to_dict,
)
from shared.models.operation import DecisionThresholds, OperationConfig

from suggestion.rule_based.inference import infer_column_type

from conversion.cells.exprs.dispatch import build_column_exprs
from conversion.pipeline import run_conversion


def test_datetime_and_time_configs_round_trip_through_column_config_union() -> None:
    adapter = TypeAdapter(ColumnConfig)

    datetime_config = adapter.validate_python(
        {"type": "datetime", "datetime_format": "%Y-%m-%d %H:%M:%S"}
    )
    time_config = adapter.validate_python({"type": "time", "time_format": "%H:%M:%S"})

    assert isinstance(datetime_config, DateTimeColumnConfig)
    assert isinstance(time_config, TimeColumnConfig)
    assert column_config_to_dict(datetime_config) == {
        "type": "datetime",
        "datetime_format": "%Y-%m-%d %H:%M:%S",
    }
    assert column_config_to_dict(time_config) == {
        "type": "time",
        "time_format": "%H:%M:%S",
    }


def test_temporal_configs_reject_non_strptime_notation() -> None:
    with pytest.raises(ValidationError):
        DateTimeColumnConfig(datetime_format="yyyy-mm-dd hh:mm:ss")

    with pytest.raises(ValidationError):
        TimeColumnConfig(time_format="hh:mm:ss")


def test_rule_based_inference_suggests_datetime_and_time_configs() -> None:
    datetime_config = infer_column_type(
        ["2026-07-10 09:15:30", "2026-07-11 10:20:45", "2026-07-12 11:25:00"],
        extended_type_detection=False,
    )
    time_config = infer_column_type(
        ["09:15:30", "10:20:45", "11:25:00"],
        extended_type_detection=False,
    )

    assert datetime_config == DateTimeColumnConfig(datetime_format="%Y-%m-%d %H:%M:%S")
    assert time_config == TimeColumnConfig(time_format="%H:%M:%S")


def test_temporal_column_exprs_cast_and_emit_type_specific_issue_labels() -> None:
    datetime_exprs = build_column_exprs(
        "created_at",
        DateTimeColumnConfig(datetime_format="%Y-%m-%d %H:%M:%S"),
        "__p_nullish__created_at",
        raw_value="__p_raw__created_at",
        normalized_raw_value="__p_lower__created_at",
    )
    time_exprs = build_column_exprs(
        "starts_at",
        TimeColumnConfig(time_format="%H:%M:%S"),
        "__p_nullish__starts_at",
        raw_value="__p_raw__starts_at",
        normalized_raw_value="__p_lower__starts_at",
    )

    assert "AS TIMESTAMP" in datetime_exprs.parse_cte_entries[0][1]
    assert "INVALID_DATETIME" in datetime_exprs.issue_expr
    assert "AS TIME" in time_exprs.parse_cte_entries[0][1]
    assert "INVALID_TIME" in time_exprs.issue_expr


def test_run_conversion_normalizes_datetime_and_time_columns() -> None:
    operation_config = OperationConfig(
        null_tokens=("", "null"),
        assign_indices=True,
        drop_empty_rows=False,
        full_raw_row=False,
        include_unique_ratio=True,
        include_per_column_parse_error_counts=False,
        approximate_unique=False,
        trace_mode="sparse",
        decision_thresholds=DecisionThresholds(ready=95.0, warning=85.0),
    )

    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                created_at VARCHAR,
                starts_at VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('2026-07-10 09:15:30', '09:15:30'),
                ('invalid', 'bad-time')
            """
        )

        run_conversion(
            conn,
            confirmed_column_config={
                "A": DateTimeColumnConfig(datetime_format="%Y-%m-%d %H:%M:%S"),
                "B": TimeColumnConfig(time_format="%H:%M:%S"),
            },
            operation_config=operation_config,
        )

        rows = conn.execute(
            """
            SELECT created_at, starts_at, _parse_error_count, _parse_issues
            FROM raw_input
            ORDER BY _row_index
            """
        ).fetchall()

    assert str(rows[0][0]) == "2026-07-10 09:15:30"
    assert str(rows[0][1]) == "09:15:30"
    assert rows[0][2] == 0
    assert rows[1][0] is None
    assert rows[1][1] is None
    assert rows[1][2] == 2
    issue_payload = json.loads(rows[1][3])
    assert issue_payload["created_at"] == {"raw": "invalid", "code": "INVALID_DATETIME"}
    assert issue_payload["starts_at"] == {"raw": "bad-time", "code": "INVALID_TIME"}
