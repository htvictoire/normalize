from pathlib import Path

import pytest

from normalize.core.engine import EngineConfig, NormalizationEngine
from normalize.stages.ingestion.contracts import HeaderMode


def _engine_config(duckdb_path: str) -> EngineConfig:
    return EngineConfig(
        rules_version="v1",
        duckdb_path=duckdb_path,
        threads=4,
        header_mode=HeaderMode.PRESENT,
        header_row_index=1,
        encoding="utf-8",
        delimiter=",",
        null_tokens=("", "null", "none", "n/a", "-"),
        boolean_true_tokens=("true", "yes", "1"),
        boolean_false_tokens=("false", "no", "0"),
        type_inference_numeric_threshold=0.95,
        type_inference_boolean_threshold=0.95,
        assign_indices=True,
        drop_empty_rows=True,
        emit_raw_row=True,
        full_raw_row=True,
        emit_parse_issues=True,
        include_unique_ratio=True,
        include_per_column_parse_error_counts=True,
        approximate_unique=False,
        decision_ready_threshold=95.0,
        decision_warning_threshold=85.0,
        trace_mode="full",
    )


def _write_sample_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "id,amount,flag",
                "1,10.5,true",
                "2,20.0,false",
                "3,30.25,true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_engine_profile_mode_returns_decision_without_artifacts(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)

    config = _engine_config(str(tmp_path / "profile.duckdb"))
    result = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out",
        config=config,
        mode="PROFILE",
    )

    assert result["status"] in {"READY", "READY_WITH_WARNINGS", "BLOCKED"}
    assert isinstance(result["quality_score"], float)
    assert isinstance(result["issues"], list)
    assert isinstance(result["fingerprint"], str)
    assert result["artifacts"] is None


def test_engine_apply_mode_writes_artifacts(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)

    config = _engine_config(str(tmp_path / "apply.duckdb"))
    result = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out",
        config=config,
        mode="APPLY",
    )

    artifacts = result["artifacts"]
    assert isinstance(artifacts, dict)
    assert Path(artifacts["normalized_parquet"]).exists()
    assert Path(artifacts["trace_parquet"]).exists()
    assert Path(artifacts["manifest_json"]).exists()


def test_engine_fingerprint_is_stable_for_same_inputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)

    base_config = _engine_config("placeholder.duckdb")
    base_config = EngineConfig(
        **{
            **base_config.__dict__,
            "emit_raw_row": False,
            "full_raw_row": False,
            "emit_parse_issues": False,
            "include_unique_ratio": False,
            "include_per_column_parse_error_counts": False,
        }
    )

    run1 = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out1",
        config=EngineConfig(
            **{**base_config.__dict__, "duckdb_path": str(tmp_path / "run1.duckdb")}
        ),
        mode="PROFILE",
    )
    run2 = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out2",
        config=EngineConfig(
            **{**base_config.__dict__, "duckdb_path": str(tmp_path / "run2.duckdb")}
        ),
        mode="PROFILE",
    )

    assert run1["fingerprint"] == run2["fingerprint"]


def test_engine_rejects_invalid_trace_mode(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    config = EngineConfig(
        **{**_engine_config(str(tmp_path / "invalid.duckdb")).__dict__, "trace_mode": "invalid"}
    )

    with pytest.raises(ValueError, match="trace_mode must be one of: full, sparse"):
        NormalizationEngine().run(
            csv_path=csv_path,
            output_dir=tmp_path / "out",
            config=config,
            mode="APPLY",
        )


def test_engine_fingerprint_changes_when_trace_mode_changes(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    base_config = _engine_config("placeholder.duckdb")

    run_full = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out_full",
        config=EngineConfig(
            **{
                **base_config.__dict__,
                "duckdb_path": str(tmp_path / "trace_full.duckdb"),
                "trace_mode": "full",
            }
        ),
        mode="PROFILE",
    )
    run_sparse = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out_sparse",
        config=EngineConfig(
            **{
                **base_config.__dict__,
                "duckdb_path": str(tmp_path / "trace_sparse.duckdb"),
                "trace_mode": "sparse",
            }
        ),
        mode="PROFILE",
    )

    assert run_full["fingerprint"] != run_sparse["fingerprint"]
