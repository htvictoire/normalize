import json
from pathlib import Path

from normalize.core.engine.config import EngineConfig
from normalize.core.engine.service import NormalizationEngine
from shared.ingestion.contracts import HeaderMode
from shared.models.column import (
    BooleanColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
)


def _sample_column_config() -> dict[str, ColumnConfig]:
    return {
        "A": IntegerColumnConfig(
            decimal_separator=".",
            thousand_separator=",",
            grouping_style="western",
        ),
        "B": DecimalColumnConfig(
            decimal_separator=".",
            thousand_separator=",",
            grouping_style="western",
            allow_leading_decimal_point=True,
        ),
        "C": BooleanColumnConfig(),
    }


def _engine_config(duckdb_path: str) -> EngineConfig:
    return EngineConfig(
        rules_version="v1",
        duckdb_path=duckdb_path,
        threads=4,
        header_mode=HeaderMode.PRESENT,
        header_row_index=1,
        encoding="utf-8",
        delimiter=",",
        decimal_separator=".",
        thousand_separator=",",
        column_config=_sample_column_config(),
        null_tokens=("", "null", "none", "n/a", "-"),
        boolean_true_tokens=("true", "yes", "1"),
        boolean_false_tokens=("false", "no", "0"),
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


def test_engine_fingerprint_changes_when_decimal_separator_changes(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    base_config = _engine_config("placeholder.duckdb")

    run_dot = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out_dot",
        config=EngineConfig(
            **{
                **base_config.__dict__,
                "duckdb_path": str(tmp_path / "dot.duckdb"),
                "decimal_separator": ".",
                "thousand_separator": ",",
            }
        ),
        mode="PROFILE",
    )
    run_comma = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out_comma",
        config=EngineConfig(
            **{
                **base_config.__dict__,
                "duckdb_path": str(tmp_path / "comma.duckdb"),
                "decimal_separator": ",",
                "thousand_separator": ".",
            }
        ),
        mode="PROFILE",
    )

    assert run_dot["fingerprint"] != run_comma["fingerprint"]


def test_engine_fingerprint_changes_when_column_config_changes(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    base_config = _engine_config("placeholder.duckdb")

    run_a = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out_a",
        config=EngineConfig(
            **{
                **base_config.__dict__,
                "duckdb_path": str(tmp_path / "a.duckdb"),
                "column_config": _sample_column_config(),
            }
        ),
        mode="PROFILE",
    )
    changed_config = _sample_column_config()
    changed_config["B"] = DecimalColumnConfig(
        decimal_separator=",",
        thousand_separator=".",
        grouping_style="western",
        allow_leading_decimal_point=True,
    )
    run_b = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out_b",
        config=EngineConfig(
            **{
                **base_config.__dict__,
                "duckdb_path": str(tmp_path / "b.duckdb"),
                "column_config": changed_config,
            }
        ),
        mode="PROFILE",
    )

    assert run_a["fingerprint"] != run_b["fingerprint"]


def test_engine_manifest_replay_config_includes_no_guessing_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    config = EngineConfig(
        **{
            **_engine_config(str(tmp_path / "manifest.duckdb")).__dict__,
            "decimal_separator": ",",
            "thousand_separator": ".",
            "column_config": {
                "A": DateColumnConfig(date_format="%d/%m/%Y"),
                "B": DecimalColumnConfig(
                    decimal_separator=",",
                    thousand_separator=".",
                    grouping_style="western",
                    allow_leading_decimal_point=True,
                ),
                "C": BooleanColumnConfig(),
            },
        }
    )
    result = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out_manifest",
        config=config,
        mode="APPLY",
    )
    manifest_path = Path(result["artifacts"]["manifest_json"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    effective_config = manifest["replay_instructions"]["effective_config"]
    assert effective_config["decimal_separator"] == ","
    assert effective_config["thousand_separator"] == "."
    assert "column_config" in effective_config
    assert effective_config["column_config"]["A"] == {
        "type": "date",
        "date_format": "%d/%m/%Y",
    }


def test_engine_emits_mixed_currency_warning_without_blocking_ready_status(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "mixed_currency.csv"
    csv_path.write_text(
        "\n".join(
            [
                "amount",
                "$100.00",
                "$110.00",
                "€120.00",
                "$130.00",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config = EngineConfig(
        **{
            **_engine_config(str(tmp_path / "mixed.duckdb")).__dict__,
            "column_config": {
                "A": CurrencyColumnConfig(
                    decimal_separator=".",
                    thousand_separator=",",
                    grouping_style="western",
                    allow_leading_decimal_point=True,
                )
            },
        }
    )
    result = NormalizationEngine().run(
        csv_path=csv_path,
        output_dir=tmp_path / "out_mixed",
        config=config,
        mode="PROFILE",
    )

    issue_codes = sorted(issue["code"] for issue in result["issues"])
    assert "MIXED_CURRENCY" in issue_codes
    assert result["status"] == "READY"
