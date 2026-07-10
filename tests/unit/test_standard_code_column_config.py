import json
import tempfile
from pathlib import Path

import pyarrow.parquet as pq
from pydantic import TypeAdapter

from shared.db.duckdb import DuckDBManager
from shared.models.column import (
    ColumnConfig,
    CountryCodeColumnConfig,
    CurrencyCodeColumnConfig,
    LanguageCodeColumnConfig,
    StringColumnConfig,
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


def test_standard_code_configs_round_trip_through_column_config_union() -> None:
    adapter = TypeAdapter(ColumnConfig)

    assert adapter.validate_python(
        {"type": "country_code", "code_format": "alpha_2"}
    ) == CountryCodeColumnConfig(code_format="alpha_2")
    assert adapter.validate_python({"type": "currency_code"}) == CurrencyCodeColumnConfig()
    assert adapter.validate_python(
        {"type": "language_code", "code_format": "alpha_3"}
    ) == LanguageCodeColumnConfig(code_format="alpha_3")


def test_rule_based_inference_suggests_standard_code_configs() -> None:
    assert infer_column_type(
        ["us", "GB", "jp"],
        extended_type_detection=True,
    ) == CountryCodeColumnConfig(code_format="alpha_2")
    assert infer_column_type(
        ["usd", "EUR", "jpy"],
        extended_type_detection=True,
    ) == CurrencyCodeColumnConfig()
    assert infer_column_type(
        ["en", "FR", "de"],
        extended_type_detection=True,
    ) == LanguageCodeColumnConfig(code_format="alpha_2")


def test_rule_based_inference_skips_standard_codes_when_extended_detection_is_disabled() -> None:
    assert infer_column_type(
        ["us", "GB", "jp"],
        extended_type_detection=False,
    ) == StringColumnConfig()
    assert infer_column_type(
        ["usd", "EUR", "jpy"],
        extended_type_detection=False,
    ) == StringColumnConfig()
    assert infer_column_type(
        ["en", "FR", "de"],
        extended_type_detection=False,
    ) == StringColumnConfig()


def test_ai_schema_excludes_standard_code_configs_when_extended_detection_is_disabled() -> None:
    fmt = CsvFormatInference()

    core_schema = fmt.output_model_for_options(False).model_json_schema()
    extended_schema = fmt.output_model_for_options(True).model_json_schema()

    assert "country_code" not in json.dumps(core_schema)
    assert "currency_code" not in json.dumps(core_schema)
    assert "language_code" not in json.dumps(core_schema)
    assert "country_code" in json.dumps(extended_schema)
    assert "currency_code" in json.dumps(extended_schema)
    assert "language_code" in json.dumps(extended_schema)


def test_standard_code_conversion_and_parquet_export() -> None:
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        output_dir = Path(tmp)
        with DuckDBManager() as conn:
            conn.execute(
                """
                CREATE TABLE raw_input (
                    country VARCHAR,
                    currency_code VARCHAR,
                    language VARCHAR
                )
                """
            )
            conn.execute(
                """
                INSERT INTO raw_input VALUES
                    ('us', 'usd', 'EN'),
                    ('ZZ', 'bad', 'zz')
                """
            )

            result = run_conversion(
                conn,
                confirmed_column_config={
                    "A": CountryCodeColumnConfig(code_format="alpha_2"),
                    "B": CurrencyCodeColumnConfig(),
                    "C": LanguageCodeColumnConfig(code_format="alpha_2"),
                },
                operation_config=_operation_config(),
            )
            rows = conn.execute(
                """
                SELECT country, currency_code, language, _parse_error_count, _parse_issues
                FROM raw_input
                ORDER BY _row_index
                """
            ).fetchall()
            artifacts = materialize_artifacts(
                conn,
                output_dir=output_dir,
                output_type="local",
                result=result,
                source_checksum="standard-code-test-source",
                issues=[],
                run_id="standard-code-e2e",
                trace_mode="sparse",
            )

        assert rows[0] == ("US", "USD", "en", 0, None)
        assert rows[1][0:4] == (None, None, None, 3)
        issue_payload = json.loads(rows[1][4])
        assert issue_payload == {
            "country": "INVALID_COUNTRY_CODE",
            "currency_code": "INVALID_CURRENCY_CODE",
            "language": "INVALID_LANGUAGE_CODE",
        }

        normalized = pq.read_table(artifacts.normalized_parquet)
        assert normalized.column_names == [
            "country",
            "currency_code",
            "language",
            "_row_index",
            "_raw_row",
            "_parse_issues",
        ]
        assert normalized.to_pydict()["country"] == ["US", None]
        assert normalized.to_pydict()["currency_code"] == ["USD", None]
        assert normalized.to_pydict()["language"] == ["en", None]
