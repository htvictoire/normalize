"""Controller-style orchestration for suggest/confirm/normalize lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

from app.infra.postgres.repository import PostgresRunRepository
from app.models.instance import InstanceModel
from app.services.normalization import NormalizationResult, NormalizationService
from app.services.suggestion import SuggestionService
from shared.models.column import ColumnConfig
from shared.models.operation import OperationConfig, RunMode
from shared.settings import get_settings


class MainController:
    """Controller matching API endpoints over local service implementations."""

    def __init__(self) -> None:
        settings = get_settings()
        self._repository = PostgresRunRepository(dsn=settings.postgres_dsn)
        self._suggestion_service = SuggestionService()
        self._normalization_service = NormalizationService()

    def suggest(
        self,
        *,
        file_path: str | Path,
        source_file_name: str,
    ) -> InstanceModel:
        """Equivalent to `POST /normalize/suggest`."""
        suggestion = self._suggestion_service.suggest(file_path=file_path)
        instance = InstanceModel.create(
            source_path=file_path,
            source_file_name=source_file_name,
            source_format=suggestion.source_format,
        )
        instance.source_checksum = suggestion.source_checksum
        instance.set_suggestion_output(
            column_labels=suggestion.column_labels,
            suggested_column_config=suggestion.suggested_column_config,
            profiling_stats=suggestion.profiling_stats,
        )
        self._repository.save(instance)
        return instance

    def confirm(
        self,
        instance_id: UUID,
        *,
        confirmed_column_config: Mapping[str, ColumnConfig],
        operation_config: OperationConfig,
    ) -> InstanceModel:
        """Equivalent to `PUT /normalize/instances/{id}/confirm`."""
        instance = self._repository.get_required(instance_id)
        confirmed = self._normalization_service.confirm_instance(
            instance,
            confirmed_column_config=confirmed_column_config,
            operation_config=operation_config,
        )
        self._repository.save(confirmed)
        return confirmed

    def get_instance(self, instance_id: UUID) -> InstanceModel | None:
        """Equivalent to `GET /normalize/instances/{id}`."""
        return self._repository.get(instance_id)

    def normalize(
        self,
        instance_id: UUID,
        *,
        output_dir: str | Path,
        mode: RunMode = "APPLY",
        rules_version: str = "v1",
    ) -> NormalizationResult:
        """Execute normalization for one confirmed instance id."""
        instance = self._repository.get_required(instance_id)
        result = self._normalization_service.normalize(
            instance,
            output_dir=output_dir,
            mode=mode,
            rules_version=rules_version,
        )
        self._repository.save(result.instance)
        return result
