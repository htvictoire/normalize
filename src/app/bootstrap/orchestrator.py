"""
Orchestration boundary for the suggest / confirm / profile / normalize lifecycle.

MainOrchestrator is the single entrypoint for both the HTTP API and the CLI.
It sequences domain services, enforces state transitions, and persists every
lifecycle step via PostgresRunRepository.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

from shared.models.instance import InstanceModel, InstanceStatus
from shared.models.instance_config import InstanceConfig
from shared.models.issues import IssueSeverity
from shared.models.profiling import ProfilingOutput
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionInput
from shared.settings import get_settings

from app.bootstrap.conversion import ConversionService
from app.bootstrap.profiling import ProfilingService
from app.bootstrap.suggestion import SuggestionService
from app.bootstrap.validation import validate_file_format
from app.bootstrap.webhook import fire_webhook
from app.infra.postgres.repository import PostgresRunRepository


class MainOrchestrator:
    def __init__(self) -> None:
        settings = get_settings()
        self._repository = PostgresRunRepository(settings.postgres_dsn)
        self._suggestion_service = SuggestionService()
        self._profiling_service = ProfilingService()
        self._conversion_service = ConversionService()

    def _duckdb_cache_path(self, instance_id: UUID) -> Path:
        settings = get_settings()
        return Path(settings.duckdb_cache_dir) / f"{instance_id}.duckdb"

    def get_instance(self, instance_id: UUID) -> InstanceModel | None:
        return self._repository.get(instance_id)

    def suggest(
        self,
        request: SuggestionInput,
    ) -> InstanceModel:
        started_at = datetime.now(UTC)
        validate_file_format(request)
        result = self._suggestion_service.suggest(request)
        instance = InstanceModel.create(
            source_file=request.source_file,
            source_file_name=request.source_file_name,
            source_type=request.source_type,
            source_file_format=request.source_file_format,
            source_checksum=request.source_checksum,
            suggestion_method=request.suggestion_method,
            extended_type_detection=request.extended_type_detection,
        )
        instance.set_suggestion_output(
            suggested_config=result.suggested_config,
            confidence=result.confidence,
            display=result.display,
        )
        instance.timings.suggest_started_at = started_at
        instance.timings.suggest_ended_at = datetime.now(UTC)
        instance.timings.estimated_pipeline_seconds = result.estimated_pipeline_seconds
        self._repository.save(instance)
        return instance

    def confirm(
        self,
        instance_id: UUID,
        confirmed_config: InstanceConfig,
        proceed_with_pipeline: bool = False,
        webhook_url: str | None = None,
    ) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        instance.webhook_url = webhook_url
        instance.confirm(confirmed_config)
        self._repository.save(instance)
        if webhook_url:
            fire_webhook(webhook_url, instance_id, instance.status)
        if proceed_with_pipeline:
            from app.worker.app import celery_app  # noqa: PLC0415
            celery_app.send_task(
                "app.worker.tasks.run_post_confirmation_pipeline",
                args=[str(instance_id)],
            )
        return instance

    def profile(self, instance_id: UUID) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        if instance.status is not InstanceStatus.CONFIRMED:
            raise ValueError("instance must be CONFIRMED before profile")

        instance.timings.profile_started_at = datetime.now(UTC)
        instance.status = InstanceStatus.PROFILING
        self._repository.save(instance)
        if instance.webhook_url:
            fire_webhook(instance.webhook_url, instance_id, instance.status)

        # CONFIRMED status guarantees confirmed_config was set atomically by confirm()
        confirmed = cast(InstanceConfig, instance.confirmed_config)
        profiling_output = self._profiling_service.profile(
            source=SourceRef(
                source_file=instance.source_file,
                source_file_name=instance.source_file_name,
                source_type=instance.source_type,
                source_file_format=instance.source_file_format,
            ),
            source_checksum=instance.source_checksum,
            confirmed_config=confirmed,
            persisted_db_path=self._duckdb_cache_path(instance_id),
        )
        instance.set_profiling_output(profiling_output)
        instance.timings.profile_ended_at = datetime.now(UTC)
        self._repository.save(instance)
        if instance.webhook_url:
            fire_webhook(instance.webhook_url, instance_id, instance.status)
        return instance

    def normalize(self, instance_id: UUID) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        if instance.status is not InstanceStatus.PROFILED:
            raise ValueError("instance must be PROFILED before normalize")
        # PROFILED status guarantees both fields were set atomically by set_profiling_output()
        # and confirm() respectively; PROFILED is only reachable from CONFIRMED.
        profiling_output = cast(ProfilingOutput, instance.profiling_output)
        confirmed = cast(InstanceConfig, instance.confirmed_config)
        if any(issue.severity is IssueSeverity.ERROR for issue in profiling_output.issues):
            raise ValueError("instance has blocking profiling issues")
        instance.timings.convert_started_at = datetime.now(UTC)
        instance.status = InstanceStatus.NORMALIZING
        self._repository.save(instance)
        if instance.webhook_url:
            fire_webhook(instance.webhook_url, instance_id, instance.status)

        settings = get_settings()
        db_cache_path = self._duckdb_cache_path(instance_id)
        result = self._conversion_service.convert(
            source=SourceRef(
                source_file=instance.source_file,
                source_file_name=instance.source_file_name,
                source_type=instance.source_type,
                source_file_format=instance.source_file_format,
            ),
            source_checksum=instance.source_checksum,
            confirmed_column_config=confirmed.column_config,
            operation_config=confirmed.operation_config,
            profiling_issues=list(profiling_output.issues),
            output_root=settings.conversion_output_dir,
            run_id=str(instance_id),
            persisted_db_path=db_cache_path,
        )
        if db_cache_path.exists():
            db_cache_path.unlink()
        instance.set_normalization_output(result)
        instance.timings.convert_ended_at = datetime.now(UTC)
        self._repository.save(instance)
        if instance.webhook_url:
            fire_webhook(instance.webhook_url, instance_id, instance.status)
        return instance
