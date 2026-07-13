from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from shared.db.duckdb import DuckDBManager
from shared.models.column import (
    ColumnConfig,
    IdentifierColumnConfig,
    IntegerColumnConfig,
    LocalizedReasons,
)
from shared.models.issues import IssueSeverity
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
        full_raw_row=False,
        include_unique_ratio=True,
        include_per_column_parse_error_counts=False,
        approximate_unique=False,
        trace_mode="sparse",
        decision_thresholds=DecisionThresholds(ready=95.0, warning=85.0),
    )


def _primary_reasons() -> LocalizedReasons:
    trio = (
        "Column name matches a primary-key naming convention.",
        "Sampled values are 100% unique.",
        "Values follow the canonical UUID/GUID format.",
    )
    return LocalizedReasons(en=trio, fr=trio, es=trio, ar=trio)


def test_identifier_config_round_trips_through_column_config_union() -> None:
    adapter = TypeAdapter(ColumnConfig)

    reasons = _primary_reasons()
    assert adapter.validate_python(
        {
            "type": "identifier",
            "identifier_kind": "primary",
            "reasons": reasons.model_dump(),
        }
    ) == IdentifierColumnConfig(identifier_kind="primary", reasons=reasons)


def test_primary_identifier_requires_reasons() -> None:
    adapter = TypeAdapter(ColumnConfig)

    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "identifier", "identifier_kind": "primary"})


def test_primary_identifier_requires_three_reasons_per_locale() -> None:
    adapter = TypeAdapter(ColumnConfig)
    reasons = _primary_reasons().model_dump()
    reasons["fr"] = ["only", "two"]

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"type": "identifier", "identifier_kind": "primary", "reasons": reasons}
        )


def test_non_primary_identifier_rejects_reasons() -> None:
    adapter = TypeAdapter(ColumnConfig)

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "type": "identifier",
                "identifier_kind": "foreign",
                "reasons": _primary_reasons().model_dump(),
            }
        )


def test_primary_identifier_rejects_overlong_reason() -> None:
    adapter = TypeAdapter(ColumnConfig)
    reasons = _primary_reasons().model_dump()
    reasons["en"] = ["ok", "also ok", "x" * 200]

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"type": "identifier", "identifier_kind": "primary", "reasons": reasons}
        )


def test_rule_based_primary_identifier_emits_localized_bounded_reasons() -> None:
    inference = infer_column(
        [
            "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
            "6ba7b812-9dad-11d1-80b4-00c04fd430c8",
        ],
        extended_type_detection=False,
        column_name="id",
    )

    assert isinstance(inference.config, IdentifierColumnConfig)
    assert inference.config.identifier_kind == "primary"
    reasons = inference.config.reasons
    assert reasons is not None
    assert "UUID" in reasons.en[2]
    assert "UUID/GUID" in reasons.fr[2]
    for locale in (reasons.en, reasons.fr, reasons.es, reasons.ar):
        assert len(locale) == 3
        assert all(len(reason) <= 160 for reason in locale)


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
    ) == IntegerColumnConfig()


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

        config = {
            "A": IdentifierColumnConfig(identifier_kind="primary", reasons=_primary_reasons())
        }
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
            column_config={
                "order_id": IdentifierColumnConfig(
                    identifier_kind="primary", reasons=_primary_reasons()
                )
            },
            null_tokens=("", "null"),
            counts_by_name=counts.column_counts,
            row_count=counts.row_count,
        )

    profile = profile_results.column_stats["order_id"].type_profile
    assert profile.profile_type == "identifier"
    assert profile.distinct_count == 2
    assert profile.duplicate_count == 1
    assert [issue.code for issue in profile_results.issues] == ["IDENTIFIER_DUPLICATES"]
    # Duplicates in a primary key are an ERROR: uniqueness is the column's whole
    # contract, and a consumer joining on it would silently multiply rows.
    assert profile_results.issues[0].severity is IssueSeverity.ERROR
    assert json.dumps(profile_results.issues[0].evidence) == (
        '{"is_primary_key": true, "duplicate_count": 1, "distinct_count": 2, '
        '"uniqueness_ratio": 0.6666666666666666}'
    )
