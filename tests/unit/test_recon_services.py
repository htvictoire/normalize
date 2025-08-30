from pathlib import Path

import pytest

from app.bootstrap import MainOrchestrator
from app.bootstrap.conversion import ConversionService
from app.bootstrap.profiling import ProfilingService
from app.bootstrap.suggestion import SuggestionService
from app.models.instance import InstanceModel, InstanceStatus
from app.persistence.repository import InMemoryNormalizationInstanceRepository
from shared.ingestion.checksum import sha256_stream
from shared.models.confirmation import ConfirmedConfig
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
    )
    instance.source_checksum = sha256_stream(csv_path)
    instance.set_suggestion_output(suggestion)
    return instance


def _confirmed_config_from_instance(
    instance: InstanceModel,
    *,
    include_unique_ratio: bool = True,
) -> ConfirmedConfig:
    assert instance.suggested_config is not None
    return ConfirmedConfig(
        source_format=instance.suggested_config.source_format,
        column_config={pos: col.config for pos, col in instance.suggested_config.columns.items()},
        operation_config=_operation_config(include_unique_ratio=include_unique_ratio),
    )


def test_suggestion_populates_instance_handoff_payload(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    suggestion_service = SuggestionService()

    result = suggestion_service.suggest(csv_path)

    assert result.row_count == 3
    assert set(result.columns.keys()) == {"A", "B", "C"}
    assert result.columns["A"].label == "id"
    assert result.columns["B"].label == "amount"
    assert result.columns["C"].label == "flag"


def test_suggestion_includes_all_15_input_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "input_15.csv"
    _write_15_column_csv(csv_path)
    suggestion_service = SuggestionService()

    result = suggestion_service.suggest(csv_path)

    assert len(result.columns) == 15
    assert set(result.columns.keys()) == {
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
    }
    assert result.columns["A"].label == "c1"
    assert result.columns["O"].label == "c15"


def test_suggestion_handles_non_canonical_headers_without_header_stage(tmp_path: Path) -> None:
    csv_path = tmp_path / "messy_headers.csv"
    _write_messy_header_csv(csv_path)
    suggestion_service = SuggestionService()

    result = suggestion_service.suggest(csv_path)

    assert result.columns["A"].label == "Order ID"
    assert result.columns["B"].label == "Gross Amount ($)"
    assert result.columns["C"].label == "Customer Name"
    assert set(result.columns.keys()) == {"A", "B", "C"}


def test_conversion_profile_mode_uses_confirmed_instance(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    conversion_service = ConversionService()
    profiling_service = ProfilingService()
    instance = _instance_from_suggestion(csv_path)
    confirmed = _confirmed_config_from_instance(instance, include_unique_ratio=False)
    instance.confirm(confirmed)
    assert instance.confirmed_config is not None

    profiling_output = profiling_service.profile(
        file_path=instance.source_r2_url,
        source_format=instance.confirmed_config.source_format,
        confirmed_column_config=instance.confirmed_config.column_config,
        operation_config=instance.confirmed_config.operation_config,
    )
    instance.set_profiling_output(profiling_output=profiling_output)
    assert instance.source_checksum is not None
    assert instance.profiling_output is not None

    result = conversion_service.convert(
        file_path=instance.source_r2_url,
        source_format=instance.confirmed_config.source_format,
        source_checksum=instance.source_checksum,
        confirmed_column_config=instance.confirmed_config.column_config,
        operation_config=instance.confirmed_config.operation_config,
        profiling_issues=instance.profiling_output.issues,
        output_dir=tmp_path / "out",
        mode="PROFILE",
    )

    assert result.status == "READY"
    assert result.artifacts is None


def test_conversion_apply_writes_artifacts(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    conversion_service = ConversionService()
    profiling_service = ProfilingService()
    instance = _instance_from_suggestion(csv_path)
    confirmed = _confirmed_config_from_instance(instance)
    instance.confirm(confirmed)
    assert instance.confirmed_config is not None

    profiling_output = profiling_service.profile(
        file_path=instance.source_r2_url,
        source_format=instance.confirmed_config.source_format,
        confirmed_column_config=instance.confirmed_config.column_config,
        operation_config=instance.confirmed_config.operation_config,
    )
    instance.set_profiling_output(profiling_output=profiling_output)
    assert instance.source_checksum is not None
    assert instance.profiling_output is not None

    result = conversion_service.convert(
        file_path=instance.source_r2_url,
        source_format=instance.confirmed_config.source_format,
        source_checksum=instance.source_checksum,
        confirmed_column_config=instance.confirmed_config.column_config,
        operation_config=instance.confirmed_config.operation_config,
        profiling_issues=instance.profiling_output.issues,
        output_dir=tmp_path / "out_apply",
        mode="APPLY",
    )

    assert result.artifacts is not None
    assert Path(result.artifacts.normalized_parquet).exists()
    assert Path(result.artifacts.trace_parquet).exists()
    assert Path(result.artifacts.manifest_json).exists()


def test_api_orchestration_flow_runs_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = tmp_path / "input.csv"
    _write_sample_csv(csv_path)
    monkeypatch.setattr(
        "app.bootstrap.orchestrator.PostgresRunRepository",
        _build_in_memory_repository,
    )
    api = MainOrchestrator()

    instance = api.suggest(
        file_path=csv_path,
        source_file_name=csv_path.name,
    )
    assert instance.suggested_config is not None
    confirmed = api.confirm(
        instance.id,
        ConfirmedConfig(
            source_format=instance.suggested_config.source_format,
            column_config={
                pos: col.config for pos, col in instance.suggested_config.columns.items()
            },
            operation_config=_operation_config(),
        ),
    )
    assert confirmed.status == InstanceStatus.CONFIRMED
    profiled = api.profile(confirmed.id)
    assert profiled.status == InstanceStatus.PROFILED
    normalized = api.normalize(profiled.id, output_dir=tmp_path / "out", mode="PROFILE")

    persisted = api.get_instance(profiled.id)
    assert persisted is not None
    assert normalized.status == InstanceStatus.READY
    assert persisted.normalization_output is not None
