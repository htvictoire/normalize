import json
from pathlib import Path
from typing import Any

import pytest

from normalize.core.column_positions import index_to_position_key
from normalize.core.engine import EngineConfig, NormalizationEngine
from normalize.stages.ingestion.contracts import HeaderMode

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

    config = _build_engine_config(
        duckdb_path=str(tmp_path / f"{case_name}.duckdb"),
        config_overrides=config_overrides,
        inferred_types=expected["inferred_types"],
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


def _build_engine_config(
    *,
    duckdb_path: str,
    config_overrides: dict[str, Any],
    inferred_types: dict[str, str],
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
        column_config=_build_column_config(config_overrides, inferred_types),
        null_tokens=("", "null", "none", "n/a", "-"),
        boolean_true_tokens=("true", "yes", "1"),
        boolean_false_tokens=("false", "no", "0"),
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


def _build_column_config(
    config_overrides: dict[str, Any],
    inferred_types: dict[str, str],
) -> dict[str, dict[str, Any]]:
    date_formats = dict(config_overrides.get("date_formats", {}))
    allow_leading_decimal_point = bool(config_overrides.get("allow_leading_decimal_point"))
    decimal_separator = str(config_overrides["decimal_separator"])
    thousand_separator = str(config_overrides["thousand_separator"])

    column_config: dict[str, dict[str, Any]] = {}
    for index, (_, inferred_type) in enumerate(inferred_types.items()):
        position_key = index_to_position_key(index)
        if inferred_type == "string":
            column_config[position_key] = {"type": "string"}
        elif inferred_type == "boolean":
            column_config[position_key] = {"type": "boolean"}
        elif inferred_type == "integer":
            column_config[position_key] = {
                "type": "integer",
                "decimal_separator": decimal_separator,
                "thousand_separator": thousand_separator,
                "grouping_style": "western",
            }
        elif inferred_type in {"decimal", "float"}:
            column_config[position_key] = {
                "type": "decimal",
                "decimal_separator": decimal_separator,
                "thousand_separator": thousand_separator,
                "grouping_style": "western",
                "allow_leading_decimal_point": allow_leading_decimal_point,
            }
        elif inferred_type == "currency":
            column_config[position_key] = {
                "type": "currency",
                "decimal_separator": decimal_separator,
                "thousand_separator": thousand_separator,
                "grouping_style": "western",
                "allow_leading_decimal_point": allow_leading_decimal_point,
            }
        elif inferred_type == "date":
            date_format = date_formats.get(position_key)
            if date_format is None:
                raise ValueError(f"missing date format for declared date column at {position_key}")
            column_config[position_key] = {
                "type": "date",
                "date_format": date_format,
            }
        else:
            raise ValueError(f"unsupported inferred type in golden dataset: {inferred_type}")
    return column_config


def _assert_quality_score(score: float, assertion: str | None) -> None:
    if assertion is None:
        return
    if assertion.startswith("< "):
        upper = float(assertion.split("< ", 1)[1])
        assert score < upper
        return
    raise ValueError(f"Unsupported quality score assertion: {assertion}")
