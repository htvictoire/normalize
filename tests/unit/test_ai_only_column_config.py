import json
import tempfile
from pathlib import Path

import pyarrow.parquet as pq
from pydantic import TypeAdapter

from shared.db.duckdb import DuckDBManager
from shared.models.column import (
    CategoricalColumnConfig,
    ColumnConfig,
    EmailColumnConfig,
    IpAddressColumnConfig,
    PhoneColumnConfig,
    UrlColumnConfig,
)
from shared.models.operation import DecisionThresholds, OperationConfig

from suggestion.ai.formats.csv import CsvFormatInference
from suggestion.rule_based.inference import infer_column_type

from conversion.artifacts import materialize_artifacts
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


def test_ai_only_configs_round_trip_through_column_config_union() -> None:
    adapter = TypeAdapter(ColumnConfig)

    assert adapter.validate_python(
        {
            "type": "categorical",
            "canonical_values": ["completed", "on_hold"],
        }
    ) == CategoricalColumnConfig(canonical_values=("completed", "on_hold"))
    assert adapter.validate_python({"type": "email"}) == EmailColumnConfig()
    assert adapter.validate_python({"type": "url"}) == UrlColumnConfig()
    assert adapter.validate_python(
        {"type": "ip_address", "version": "v4"}
    ) == IpAddressColumnConfig(version="v4")
    assert adapter.validate_python({"type": "phone"}) == PhoneColumnConfig()


def test_categorical_matches_case_insensitively_and_never_nulls() -> None:
    """Case/whitespace variants normalize to the canonical spelling; unknowns are kept + flagged."""
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (region VARCHAR)")
        conn.execute(
            "INSERT INTO raw_input VALUES (' Europe '), ('ASIA'), ('asia'), ('Atlantis')"
        )
        run_conversion(
            conn,
            confirmed_column_config={
                "A": CategoricalColumnConfig(canonical_values=("Europe", "Asia"))
            },
            operation_config=_operation_config(),
        )
        rows = conn.execute(
            "SELECT region, _parse_error_count FROM raw_input ORDER BY _row_index"
        ).fetchall()

    # ' Europe ' trimmed and 'ASIA'/'asia' case-folded to the canonical spelling;
    # 'Atlantis' is unknown, so it is kept and flagged.
    assert rows == [("Europe", 0), ("Asia", 0), ("Asia", 0), ("Atlantis", 1)]


def test_rule_based_inference_does_not_suggest_ai_only_configs() -> None:
    assert infer_column_type(
        ["Complete", "On hold", "Refunded"],
        extended_type_detection=True,
    ).type != "categorical"
    assert infer_column_type(
        ["a@example.com", "b@example.com", "c@example.com"],
        extended_type_detection=True,
    ).type != "email"
    assert infer_column_type(
        ["+14155552671", "+442071838750", "+33142685300"],
        extended_type_detection=True,
    ).type != "phone"


def test_ai_schema_gates_ai_only_configs_to_extended_detection() -> None:
    fmt = CsvFormatInference()

    core_schema = json.dumps(fmt.output_model_for_options(False).model_json_schema())
    extended_schema = json.dumps(fmt.output_model_for_options(True).model_json_schema())

    for type_name in ("categorical", "email", "url", "ip_address", "phone"):
        assert type_name not in core_schema
        assert type_name in extended_schema


def test_ai_only_conversion_and_parquet_export() -> None:
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        output_dir = Path(tmp)
        with DuckDBManager() as conn:
            conn.execute(
                """
                CREATE TABLE raw_input (
                    status VARCHAR,
                    email VARCHAR,
                    website VARCHAR,
                    ip VARCHAR,
                    phone VARCHAR
                )
                """
            )
            conn.execute(
                """
                INSERT INTO raw_input VALUES
                    (
                        'COMPLETED',
                        'USER@Example.COM',
                        'https://example.com/a',
                        '192.168.0.1',
                        '+1 (415) 555-2671'
                    ),
                    (
                        'Unexpected',
                        'not-email',
                        'ftp://example.com',
                        '999.0.0.1',
                        '415-555-2671'
                    )
                """
            )

            result = run_conversion(
                conn,
                confirmed_column_config={
                    "A": CategoricalColumnConfig(
                        canonical_values=("completed", "on_hold"),
                    ),
                    "B": EmailColumnConfig(),
                    "C": UrlColumnConfig(),
                    "D": IpAddressColumnConfig(version="any"),
                    "E": PhoneColumnConfig(),
                },
                operation_config=_operation_config(),
            )
            rows = conn.execute(
                """
                SELECT status, email, website, ip, phone, _parse_error_count, _parse_issues
                FROM raw_input
                ORDER BY _row_index
                """
            ).fetchall()
            artifacts = materialize_artifacts(
                conn,
                output_dir=output_dir,
                output_type="local",
                result=result,
                source_checksum="ai-only-test-source",
                issues=[],
                run_id="ai-only-e2e",
                trace_mode="sparse",
            )

        assert rows[0] == (
            "completed",
            "user@example.com",
            "https://example.com/a",
            "192.168.0.1",
            "+14155552671",
            0,
            None,
        )
        # 'Unexpected' is not canonical: it is KEPT (never nulled) and flagged.
        assert rows[1][0:6] == ("Unexpected", None, None, None, None, 5)
        issue_payload = json.loads(rows[1][6])
        assert issue_payload == {
            "status": "INVALID_CATEGORICAL",
            "email": "INVALID_EMAIL",
            "website": "INVALID_URL",
            "ip": "INVALID_IP_ADDRESS",
            "phone": "INVALID_PHONE",
        }

        normalized = pq.read_table(artifacts.normalized_parquet)
        assert normalized.column_names == [
            "status",
            "email",
            "website",
            "ip",
            "phone",
            "_row_index",
            "_raw_row",
            "_parse_issues",
        ]
        assert normalized.to_pydict()["status"] == ["completed", "Unexpected"]
        assert normalized.to_pydict()["email"] == ["user@example.com", None]
        assert normalized.to_pydict()["phone"] == ["+14155552671", None]
