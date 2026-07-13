"""
Orchestration boundary for the suggest / confirm / profile / normalize lifecycle.

MainOrchestrator is the single entrypoint for both the HTTP API and the CLI.
It sequences domain services, enforces state transitions, and persists every
lifecycle step via PostgresRunRepository.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from shared.models.instance import InstanceModel, InstanceStatus
from shared.models.instance_config import InstanceConfig
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionInput
from shared.settings import get_settings

from app.bootstrap.conversion import ConversionService
from app.bootstrap.profiling import ProfilingService
from app.bootstrap.suggestion import SuggestionService
from app.bootstrap.validation import validate_auto_confirm, validate_file_format
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

    def _enqueue_post_confirmation_pipeline(self, instance_id: UUID) -> None:
        from app.worker.app import celery_app  # noqa: PLC0415

        celery_app.send_task(
            "app.worker.tasks.run_post_confirmation_pipeline",
            args=[str(instance_id)],
        )

    def suggest(
        self,
        request: SuggestionInput,
    ) -> InstanceModel:
        started_at = datetime.now(UTC)
        validate_auto_confirm(request)
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
        if request.auto_confirm:
            instance.confirm(result.suggested_config)
            self._repository.save(instance)
            if request.auto_normalize:
                self._enqueue_post_confirmation_pipeline(instance.instance_id)
        return instance

    def confirm(
        self,
        instance_id: UUID,
        confirmed_config: InstanceConfig,
        auto_normalize: bool = False,
        webhook_url: str | None = None,
    ) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        instance.webhook_url = webhook_url
        instance.confirm(confirmed_config)
        self._repository.save(instance)
        if webhook_url:
            fire_webhook(webhook_url, instance_id, instance.status)
        if auto_normalize:
            self._enqueue_post_confirmation_pipeline(instance_id)
        return instance

    def mark_failed(self, instance_id: UUID, reason: str) -> InstanceModel:
        """Record a final failure and notify. Called when worker retries are exhausted."""
        instance = self._repository.get_required(instance_id)
        instance.fail(reason)
        self._repository.save(instance)
        if instance.webhook_url:
            fire_webhook(instance.webhook_url, instance_id, instance.status)
        return instance

    @contextmanager
    def _terminal_on_error(self, instance: InstanceModel) -> Iterator[None]:
        """Guarantee a phase never leaves an instance frozen in an in-flight status.

        Any exception persists FAILED with its cause and re-raises. It deliberately
        does not fire the webhook: the worker owns that once retries are exhausted,
        and a synchronous caller receives the exception itself.
        """
        try:
            yield
        except Exception as exc:
            instance.fail(f"{type(exc).__name__}: {exc}")
            self._repository.save(instance)
            raise

    def _advance(self, instance: InstanceModel, status: InstanceStatus) -> None:
        instance.begin_phase(status)
        self._repository.save(instance)
        if instance.webhook_url:
            fire_webhook(instance.webhook_url, instance.instance_id, status)

    def profile(self, instance_id: UUID) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        # The precondition is a confirmed config, not a particular status: a retry
        # re-enters from whatever state the failed attempt left behind.
        confirmed = instance.confirmed_config
        if confirmed is None:
            raise ValueError("instance must be CONFIRMED before profile")

        # Discard any cache a previous attempt half-wrote; profiling rebuilds it.
        cache_path = self._duckdb_cache_path(instance_id)
        cache_path.unlink(missing_ok=True)

        instance.timings.profile_started_at = datetime.now(UTC)
        self._advance(instance, InstanceStatus.PROFILING)

        with self._terminal_on_error(instance):
            profiling_output = self._profiling_service.profile(
                source=SourceRef(
                    source_file=instance.source_file,
                    source_file_name=instance.source_file_name,
                    source_type=instance.source_type,
                    source_file_format=instance.source_file_format,
                ),
                source_checksum=instance.source_checksum,
                confirmed_config=confirmed,
                persisted_db_path=cache_path,
            )
        instance.set_profiling_output(profiling_output)
        instance.timings.profile_ended_at = datetime.now(UTC)
        self._repository.save(instance)
        if instance.webhook_url:
            fire_webhook(instance.webhook_url, instance_id, instance.status)
        return instance

    def normalize(self, instance_id: UUID) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        # As in profile(): the precondition is the output of the prior phase, not a
        # status, so a retry can re-enter from whatever the failed attempt left.
        profiling_output = instance.profiling_output
        confirmed = instance.confirmed_config
        if profiling_output is None or confirmed is None:
            raise ValueError("instance must be PROFILED before normalize")

        # A blocking issue does not skip conversion. BLOCKED is a verdict, and the
        # artifacts are the evidence for it: a consumer told its primary key has
        # duplicates needs the parquet and trace to find them. The status is decided
        # after conversion, by evaluate_decision, from these same issues.
        instance.timings.convert_started_at = datetime.now(UTC)
        self._advance(instance, InstanceStatus.NORMALIZING)

        settings = get_settings()
        db_cache_path = self._duckdb_cache_path(instance_id)
        with self._terminal_on_error(instance):
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
                column_stats=profiling_output.column_stats,
                output_root=settings.conversion_output_dir,
                run_id=str(instance_id),
                persisted_db_path=db_cache_path,
            )
        db_cache_path.unlink(missing_ok=True)
        instance.set_normalization_output(
            result,
            issues=profiling_output.issues,
            thresholds=confirmed.operation_config.decision_thresholds,
        )
        instance.timings.convert_ended_at = datetime.now(UTC)
        self._repository.save(instance)
        if instance.webhook_url:
            fire_webhook(instance.webhook_url, instance_id, instance.status)
        return instance
