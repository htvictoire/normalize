"""
Application orchestration boundary for the normalization lifecycle.

`MainOrchestrator` is the transport-agnostic entrypoint used by both:
- HTTP routes in `app.api.router`
- any local callers that want the same lifecycle behavior without HTTP

The controller intentionally does not implement heavy business logic itself.
It coordinates domain services and persistence in a deterministic sequence so
that API and non-API callers get identical state transitions and error
semantics.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.bootstrap.conversion import ConversionService
from app.bootstrap.profiling import ProfilingService
from app.bootstrap.suggestion import SuggestionService
from app.bootstrap.validation import validate_file_format
from app.infra.postgres.repository import PostgresRunRepository
from app.models.instance import InstanceModel, InstanceStatus
from shared.ingestion.checksum import sha256_stream
from shared.models.confirmation import ConfirmedConfig
from shared.models.issues import IssueSeverity
from shared.models.normalization import NormalizationOutput
from shared.models.operation import FileFormat, RunMode
from shared.settings import get_settings


class MainOrchestrator:
    """
    Orchestrator for suggest -> confirm -> profile -> normalize workflow.

    Responsibilities:
    - construct and hold service/repository dependencies
    - enforce persistence around each lifecycle transition
    - provide one stable contract for both API handlers and CLI tooling

    Non-responsibilities:
    - no parsing/inference logic
    - no conversion SQL execution logic
    - no direct persistence schema logic

    Those concerns are delegated to `SuggestionService`, `ProfilingService`,
    `ConversionService`, and `PostgresRunRepository`.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._repository = PostgresRunRepository(dsn=settings.postgres_dsn)
        self._suggestion_service = SuggestionService()
        self._profiling_service = ProfilingService()
        self._conversion_service = ConversionService()

    def get_instance(self, instance_id: UUID) -> InstanceModel | None:
        return self._repository.get(instance_id)

    def suggest(
        self,
        *,
        file_path: str | Path,
        source_file_name: str,
        format_type: FileFormat,
    ) -> InstanceModel:
        source_path = Path(file_path)
        validate_file_format(source_path, format_type)
        suggestion = self._suggestion_service.suggest(
            file_path=source_path,
            format_type=format_type,
        )
        instance = InstanceModel.create(
            source_path=source_path,
            source_file_name=source_file_name,
            format_type=format_type,
        )
        instance.source_checksum = sha256_stream(source_path)
        instance.set_suggestion_output(suggestion)
        self._repository.save(instance)
        return instance

    def confirm(self, instance_id: UUID, confirmed_config: ConfirmedConfig) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        instance.confirm(confirmed_config)
        self._repository.save(instance)
        return instance

    def profile(self, instance_id: UUID) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        if instance.status is not InstanceStatus.CONFIRMED:
            raise ValueError("instance must be CONFIRMED before profile")
        if instance.confirmed_config is None:
            raise ValueError("instance is missing confirmed config")

        instance.status = InstanceStatus.PROFILING
        self._repository.save(instance)

        confirmed = instance.confirmed_config
        profiling_output = self._profiling_service.profile(
            file_path=instance.source_r2_url,
            source_format=confirmed.source_format,
            confirmed_column_config=confirmed.column_config,
            operation_config=confirmed.operation_config,
        )
        instance.set_profiling_output(profiling_output=profiling_output)
        self._repository.save(instance)
        return instance

    def normalize(
        self,
        instance_id: UUID,
        *,
        output_dir: str | Path,
        mode: RunMode = "APPLY",
        rules_version: str = "v1",
    ) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        if instance.status is not InstanceStatus.PROFILED:
            raise ValueError("instance must be PROFILED before normalize")
        if instance.confirmed_config is None:
            raise ValueError("instance is missing confirmed config")
        if instance.profiling_output is None:
            raise ValueError("instance is missing profiling output")
        if any(
            issue.severity is IssueSeverity.ERROR for issue in instance.profiling_output.issues
        ):
            raise ValueError("instance has blocking profiling issues")
        if instance.source_checksum is None:
            raise ValueError("instance is missing source checksum")

        instance.status = InstanceStatus.NORMALIZING
        self._repository.save(instance)

        confirmed = instance.confirmed_config
        result = self._conversion_service.convert(
            file_path=instance.source_r2_url,
            source_format=confirmed.source_format,
            source_checksum=instance.source_checksum,
            confirmed_column_config=confirmed.column_config,
            operation_config=confirmed.operation_config,
            profiling_issues=list(instance.profiling_output.issues),
            output_dir=output_dir,
            mode=mode,
            rules_version=rules_version,
        )
        instance.set_normalization_output(
            normalization_output=NormalizationOutput(
                fingerprint=result.fingerprint,
                quality_output=result.quality_output,
                artifacts=result.artifacts,
            )
        )
        self._repository.save(instance)
        return instance
