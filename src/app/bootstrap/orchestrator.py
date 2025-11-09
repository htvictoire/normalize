"""
Orchestration boundary for the suggest / confirm / profile / normalize lifecycle.

MainOrchestrator is the single entrypoint for both the HTTP API and the CLI.
It sequences domain services, enforces state transitions, and persists every
lifecycle step via PostgresRunRepository.
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
from shared.models.confirmation import ConfirmedConfig
from shared.models.issues import IssueSeverity
from shared.models.normalization import NormalizationOutput
from shared.models.source import SourceRef
from shared.settings import get_settings


class MainOrchestrator:
    def __init__(self) -> None:
        settings = get_settings()
        self._repository = PostgresRunRepository(dsn=settings.postgres_dsn)
        self._suggestion_service = SuggestionService()
        self._profiling_service = ProfilingService()
        self._conversion_service = ConversionService()

    def get_instance(self, instance_id: UUID) -> InstanceModel | None:
        return self._repository.get(instance_id)

    def suggest(self, source: SourceRef, *, source_checksum: str) -> InstanceModel:
        validate_file_format(source)
        suggestion = self._suggestion_service.suggest(source)
        instance = InstanceModel.create(
            source_file=source.source_file,
            source_file_name=source.source_file_name,
            source_type=source.source_type,
            source_file_format=source.source_file_format,
        )
        instance.source_checksum = source_checksum
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
            source=SourceRef(
                source_file=instance.source_file,
                source_file_name=instance.source_file_name,
                source_type=instance.source_type,
                source_file_format=instance.source_file_format,
            ),
            source_checksum=instance.source_checksum or "",
            source_format=confirmed.source_format,
            confirmed_column_config=confirmed.column_config,
            operation_config=confirmed.operation_config,
        )
        instance.set_profiling_output(profiling_output=profiling_output)
        self._repository.save(instance)
        return instance

    def normalize(self, instance_id: UUID) -> InstanceModel:
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

        settings = get_settings()
        output_root = Path(settings.conversion_output_dir) / str(instance_id)

        confirmed = instance.confirmed_config
        result = self._conversion_service.convert(
            source=SourceRef(
                source_file=instance.source_file,
                source_file_name=instance.source_file_name,
                source_type=instance.source_type,
                source_file_format=instance.source_file_format,
            ),
            source_format=confirmed.source_format,
            source_checksum=instance.source_checksum,
            confirmed_column_config=confirmed.column_config,
            operation_config=confirmed.operation_config,
            profiling_issues=list(instance.profiling_output.issues),
            output_root=output_root,
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
