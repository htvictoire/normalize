from __future__ import annotations

from uuid import UUID

from shared.models.instance import InstanceModel, InstanceStatus
from shared.models.instance_config import InstanceConfig
from shared.models.operation import CsvSourceFormat, DecisionThresholds, OperationConfig
from shared.models.profiling import ColumnCounts
from shared.models.suggestion import (
    SuggestedColumnDisplay,
    SuggestionConfidence,
    SuggestionDisplay,
    SuggestionInput,
    SuggestionOutput,
)

from app.bootstrap.orchestrator import MainOrchestrator


def _suggested_config() -> InstanceConfig:
    return InstanceConfig(
        source_format=CsvSourceFormat(
            encoding="utf-8",
            delimiter=",",
            header_mode="present",
            header_row_index=1,
        ),
        column_config={"A": {"type": "string"}},
        operation_config=OperationConfig(
            null_tokens=("", "null"),
            assign_indices=True,
            drop_empty_rows=False,
            full_raw_row=False,
            include_unique_ratio=True,
            include_per_column_parse_error_counts=False,
            approximate_unique=False,
            trace_mode="sparse",
            decision_thresholds=DecisionThresholds(ready=95.0, warning=85.0),
        ),
    )


class _FakeSuggestionService:
    def __init__(self, suggested_config: InstanceConfig) -> None:
        self._suggested_config = suggested_config

    def suggest(self, _request: SuggestionInput) -> SuggestionOutput:
        return SuggestionOutput(
            suggested_config=self._suggested_config,
            confidence=SuggestionConfidence(column_config={"A": 1.0}),
            display=SuggestionDisplay(
                row_count=1,
                columns={
                    "A": SuggestedColumnDisplay(
                        label="name",
                        counts=ColumnCounts(
                            null_count=0,
                            nullish_count=0,
                            non_null_count=1,
                            non_nullish_count=1,
                        ),
                        sample_values=["alice"],
                    )
                },
                sample_rows=[["alice"]],
            ),
            estimated_pipeline_seconds=1,
        )


class _FakeRepository:
    def __init__(self) -> None:
        self.saved: list[InstanceModel] = []

    def save(self, instance: InstanceModel) -> InstanceModel:
        self.saved.append(instance.model_copy(deep=True))
        return instance


def test_suggest_can_auto_confirm_and_auto_normalize(monkeypatch) -> None:
    suggested_config = _suggested_config()
    repository = _FakeRepository()
    enqueued: list[UUID] = []
    orchestrator = object.__new__(MainOrchestrator)
    orchestrator._repository = repository
    orchestrator._suggestion_service = _FakeSuggestionService(suggested_config)

    def enqueue(instance_id: UUID) -> None:
        enqueued.append(instance_id)

    monkeypatch.setattr("app.bootstrap.orchestrator.validate_file_format", lambda _: None)
    monkeypatch.setattr(
        orchestrator,
        "_enqueue_post_confirmation_pipeline",
        enqueue,
    )

    instance = orchestrator.suggest(
        SuggestionInput(
            source_file="input.csv",
            source_file_name="input.csv",
            source_type="local",
            source_file_format="csv",
            source_checksum="a" * 64,
            suggestion_method="rule_based",
            extended_type_detection=False,
            auto_confirm=True,
            auto_normalize=True,
        )
    )

    assert instance.status is InstanceStatus.CONFIRMED
    assert instance.confirmed_config == suggested_config
    assert enqueued == [instance.instance_id]
    assert [saved.status for saved in repository.saved] == [
        InstanceStatus.AWAITING_CONFIRMATION,
        InstanceStatus.CONFIRMED,
    ]
