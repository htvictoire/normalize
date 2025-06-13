import json
from pathlib import Path
from typing import Any

import pytest

from normalize.core.duckdb_manager import DuckDBManager
from normalize.core.engine import EngineConfig, NormalizationEngine
from normalize.stages.header_canonicalization import HeaderCanonicalizationStage
from normalize.stages.ingestion import IngestionStage
from normalize.stages.ingestion.contracts import HeaderMode
from normalize.stages.type_inference import TypeInferenceStage

_TOKEN_ARGS = {
    "null_tokens": ["", "null", "none", "n/a", "-"],
    "boolean_true_tokens": ["true", "yes", "1"],
    "boolean_false_tokens": ["false", "no", "0"],
}
_GOLDEN_ROOT = Path(__file__).resolve().parents[1] / "golden_datasets"


def _golden_case_names() -> list[str]:
    return sorted(path.name for path in _GOLDEN_ROOT.iterdir() if path.is_dir())


@pytest.mark.parametrize("case_name", _golden_case_names())
def test_phase15_golden_datasets(case_name: str, tmp_path: Path) -> None:
    case_root = _GOLDEN_ROOT / case_name
    expected_payload = json.loads((case_root / "expected.json").read_text(encoding="utf-8"))
    config_overrides = expected_payload["config"]
    expected = expected_payload["expected"]
    input_csv = case_root / "input.csv"

    inferred_types = _infer_types_for_case(input_csv, config_overrides)
    assert inferred_types == expected["inferred_types"]

    config = _build_engine_config(
        duckdb_path=str(tmp_path / f"{case_name}.duckdb"),
        config_overrides=config_overrides,
    )
    result = NormalizationEngine().run(
        csv_path=input_csv,
        output_dir=tmp_path / f"{case_name}_out",
        config=config,
        mode="PROFILE",
    )

    issue_codes = sorted(issue["code"] for issue in result["issues"])
    assert issue_codes == sorted(expected["issue_codes"])
    assert result["status"] == expected["status"]
    _assert_quality_score(result["quality_score"], expected.get("quality_score_assertion"))


def _infer_types_for_case(
    input_csv: Path,
    config_overrides: dict[str, Any],
) -> dict[str, str]:
    with DuckDBManager() as conn:
        ingestion = IngestionStage()
        ingestion.execute(
            conn,
            input_csv,
            header_mode=HeaderMode.PRESENT,
            header_row_index=1,
            encoding="utf-8",
            delimiter=",",
        )
        HeaderCanonicalizationStage().execute(conn)
        inference = TypeInferenceStage(
            numeric_threshold=0.95,
            boolean_threshold=0.95,
            currency_threshold=0.50,
        )
        return inference.execute(
            conn,
            **_TOKEN_ARGS,
            decimal_separator=config_overrides["decimal_separator"],
            thousand_separator=config_overrides["thousand_separator"],
            allow_leading_decimal_point=config_overrides["allow_leading_decimal_point"],
            date_formats=config_overrides["date_formats"],
        )


def _build_engine_config(
    *,
    duckdb_path: str,
    config_overrides: dict[str, Any],
) -> EngineConfig:
    return EngineConfig(
        rules_version="v1",
        duckdb_path=duckdb_path,
        threads=4,
        header_mode=HeaderMode.PRESENT,
        header_row_index=1,
        encoding="utf-8",
        delimiter=",",
        decimal_separator=config_overrides["decimal_separator"],
        thousand_separator=config_overrides["thousand_separator"],
        allow_leading_decimal_point=config_overrides["allow_leading_decimal_point"],
        date_formats=config_overrides["date_formats"],
        null_tokens=("", "null", "none", "n/a", "-"),
        boolean_true_tokens=("true", "yes", "1"),
        boolean_false_tokens=("false", "no", "0"),
        type_inference_numeric_threshold=0.95,
        type_inference_boolean_threshold=0.95,
        type_inference_currency_threshold=0.50,
        assign_indices=True,
        drop_empty_rows=True,
        emit_raw_row=False,
        full_raw_row=False,
        emit_parse_issues=False,
        include_unique_ratio=False,
        include_per_column_parse_error_counts=False,
        approximate_unique=False,
        decision_ready_threshold=95.0,
        decision_warning_threshold=85.0,
        trace_mode="sparse",
    )


def _assert_quality_score(score: float, assertion: str | None) -> None:
    if assertion is None:
        return
    if assertion.startswith("< "):
        upper = float(assertion.split("< ", 1)[1])
        assert score < upper
        return
    raise ValueError(f"Unsupported quality score assertion: {assertion}")
