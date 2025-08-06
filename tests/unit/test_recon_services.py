from pathlib import Path

import pytest

from app.api.controllers import MainController
from app.models.instance import InstanceModel, InstanceStatus
from app.persistence.repository import InMemoryNormalizationInstanceRepository
from app.services.normalization import NormalizationService
from app.services.suggestion import SuggestionService
from shared.models.operation import (
    DecisionThresholds,
    OperationConfig,
)


def _build_in_memory_repository(*, dsn: str) -> InMemoryNormalizationInstanceRepository:
    _ = dsn
    return InMemoryNormalizationInstanceRepository()


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


def _operation_config(*, include_unique_ratio: bool = True) -> OperationConfig:
    return OperationConfig(
        null_tokens=("", "null", "none", "n/a", "-"),
        boolean_true_tokens=("true", "yes", "1"),
        boolean_false_tokens=("false", "no", "0"),
        assign_indices=True,
        drop_empty_rows=True,
        emit_raw_row=True,
        full_raw_row=False,
        emit_parse_issues=True,
        include_unique_ratio=include_unique_ratio,
        include_per_column_parse_error_counts=False,
        approximate_unique=False,
        trace_mode="sparse",
        decision_thresholds=DecisionThresholds(ready=95.0, warning=85.0),
    )


def _write_15_column_csv(path: Path) -> None:
    header = ",".join([f"c{i}" for i in range(1, 16)])
    row1 = ",".join(str(i) for i in range(1, 16))
    row2 = ",".join(str(i * 2) for i in range(1, 16))
    path.write_text(f"{header}\n{row1}\n{row2}\n", encoding="utf-8")


def _write_messy_header_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "Order ID,Gross Amount ($),Customer Name",
                "1,10.50,Alice",
                "2,20.75,Bob",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _instance_from_suggestion(csv_path: Path) -> InstanceModel:
    suggestion_service = SuggestionService()
    suggestion = suggestion_service.suggest(csv_path)
    instance = InstanceModel.create(
        source_path=csv_path,
        source_file_name=csv_path.name,
        source_format=suggestion.source_format,
    )
    instance.source_checksum = suggestion.source_checksum
    instance.set_suggestion_output(
        column_labels=suggestion.column_labels,
        suggested_column_config=suggestion.suggested_column_config,
        profiling_stats=suggestion.profiling_stats,
    )
    return instance


def test_suggest_populates_instance_handoff_payload(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    suggestion_service = SuggestionService()

    result = suggestion_service.suggest(csv_path)

    assert result.source_checksum
    assert result.profiling_stats.row_count == 3
    assert result.column_labels == {"A": "id", "B": "amount", "C": "flag"}
    assert set(result.suggested_column_config.keys()) == {"A", "B", "C"}


def test_suggest_includes_all_15_input_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "input_15.csv"
    _write_15_column_csv(csv_path)
    suggestion_service = SuggestionService()

    result = suggestion_service.suggest(csv_path)

    assert len(result.suggested_column_config) == 15
    assert set(result.suggested_column_config.keys()) == {
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
        "J",
        "K",
        "L",
        "M",
        "N",
        "O",
    }
    assert set(result.profiling_stats.columns) == {
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
        "J",
        "K",
        "L",
        "M",
        "N",
        "O",
    }
    assert result.column_labels["A"] == "c1"
    assert result.column_labels["O"] == "c15"


def test_suggest_handles_non_canonical_headers_without_header_stage(tmp_path: Path) -> None:
    csv_path = tmp_path / "messy_headers.csv"
    _write_messy_header_csv(csv_path)
    suggestion_service = SuggestionService()

    result = suggestion_service.suggest(csv_path)

    assert result.column_labels == {
        "A": "Order ID",
        "B": "Gross Amount ($)",
        "C": "Customer Name",
    }
    assert set(result.profiling_stats.columns) == {"A", "B", "C"}


def test_normalize_profile_uses_confirmed_instance(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    normalization_service = NormalizationService()
    instance = _instance_from_suggestion(csv_path)
    normalization_service.confirm_instance(
        instance,
        confirmed_column_config=instance.suggested_column_config,
        operation_config=_operation_config(include_unique_ratio=False),
    )

    result = normalization_service.normalize(
        instance,
        output_dir=tmp_path / "out",
        mode="PROFILE",
    )

    assert result.status in {"READY", "READY_WITH_WARNINGS", "BLOCKED"}
    assert result.artifacts is None
    assert "shared_profiling" not in result.stage_metrics
    assert "type_inference" not in result.stage_metrics
    assert instance.normalization_output is not None


def test_normalize_apply_writes_artifacts(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    normalization_service = NormalizationService()
    instance = _instance_from_suggestion(csv_path)
    normalization_service.confirm_instance(
        instance,
        confirmed_column_config=instance.suggested_column_config,
        operation_config=_operation_config(),
    )

    result = normalization_service.normalize(
        instance,
        output_dir=tmp_path / "out_apply",
        mode="APPLY",
    )

    assert result.artifacts is not None
    assert Path(result.artifacts["normalized_parquet"]).exists()
    assert Path(result.artifacts["trace_parquet"]).exists()
    assert Path(result.artifacts["manifest_json"]).exists()


def test_api_orchestration_flow_runs_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    monkeypatch.setattr(
        "app.api.controllers.PostgresRunRepository",
        _build_in_memory_repository,
    )
    api = MainController()

    instance = api.suggest(
        file_path=csv_path,
        source_file_name=csv_path.name,
    )
    confirmed = api.confirm(
        instance.id,
        confirmed_column_config=instance.suggested_column_config,
        operation_config=_operation_config(),
    )
    assert confirmed.status == InstanceStatus.NORMALIZING
    result = api.normalize(confirmed.id, output_dir=tmp_path / "out", mode="PROFILE")

    persisted = api.get_instance(confirmed.id)
    assert persisted is not None
    assert result.status in {"READY", "READY_WITH_WARNINGS", "BLOCKED"}
    assert persisted.normalization_output is not None
