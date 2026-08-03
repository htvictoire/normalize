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

from shared.errors import InvalidRequestError, InvalidStateError, SourceError
from shared.models.instance import InstanceModel, InstanceStatus
from shared.models.instance_config import InstanceConfig
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionInput
from shared.settings import get_settings

from app.bootstrap.conversion import ConversionService
from app.bootstrap.profiling import ProfilingService
from app.bootstrap.suggestion import SuggestionService
from app.bootstrap.validation import validate_file_format, validate_source_path
from app.bootstrap.webhook import send_webhook
from app.infra.postgres.repository import PostgresRunRepository
from app.worker.tasks import run_suggestion_task


def _suggestion_input(instance: InstanceModel) -> SuggestionInput:
    """Rebuild the request a stored instance was created from."""
    return SuggestionInput(
        source_file=instance.source_file,
        source_file_name=instance.source_file_name,
        source_type=instance.source_type,
        source_file_format=instance.source_file_format,
        source_checksum=instance.source_checksum,
        layout_method=instance.layout_method,
        typing_method=instance.typing_method,
        extended_type_detection=instance.extended_type_detection,
        webhook_url=instance.webhook_url,
    )


def _with_columns(config: InstanceConfig) -> InstanceConfig:
    """Return the config, rejecting one that declares no columns.

    A source with no columns has nothing to normalize. Rejected at the boundary
    it enters rather than left to fail downstream, where the absence surfaces as
    an internal lookup error.
    """
    if not config.column_config:
        raise SourceError("The configuration declares no columns.")
    return config


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

    def _notify(self, instance: InstanceModel) -> None:
        """Deliver the complete current instance to its webhook, if one is set."""
        if not instance.webhook_url:
            return
        send_webhook(instance.webhook_url, instance)

    def suggest(self, request: SuggestionInput) -> InstanceModel:
        """Schedule both suggestion phases in the background, returning immediately.

        Layout and typing are both network-bound (AI calls, or a full source read);
        nothing about the caller waiting for them helps, so this always dispatches
        to a background task rather than blocking the request. A caller that wants
        the result inline uses resolve_layout() then type_columns() instead, which
        stay synchronous and still require a real source_file.
        """
        instance = self._create_source_instance(request)
        instance.timings.suggest_started_at = datetime.now(UTC)
        self._repository.save(instance)
        run_suggestion_task.delay(str(instance.instance_id), request.model_dump(mode="json"))
        return instance

    def resolve_layout(self, request: SuggestionInput) -> InstanceModel:
        """Run the layout phase alone, leaving the instance ready to be typed."""
        if request.source_file is None:
            raise InvalidRequestError(
                "The layout phase requires source_file. Only suggest() accepts a "
                "draft, sample-only source."
            )
        started_at = datetime.now(UTC)
        instance = self._create_source_instance(request)
        instance.set_layout_output(self._suggestion_service.resolve_layout(request))
        instance.timings.suggest_started_at = started_at
        self._repository.save(instance)
        self._notify(instance)
        return instance

    def type_columns(self, instance_id: UUID) -> InstanceModel:
        """Type the columns of an instance whose layout is already resolved."""
        instance = self._repository.get_required(instance_id)
        if instance.is_draft:
            raise InvalidStateError(
                f"instance {instance_id} is a draft; attach a source_file at confirm first"
            )
        layout = instance.layout_output
        if layout is None:
            raise InvalidStateError(f"instance {instance_id} has no resolved layout")
        instance.set_typing_output(
            self._suggestion_service.type_columns(_suggestion_input(instance), layout)
        )
        instance.timings.suggest_ended_at = datetime.now(UTC)
        self._repository.save(instance)
        self._notify(instance)
        return instance

    def create_confirmed(
        self,
        request: SuggestionInput,
        confirmed_config: InstanceConfig,
    ) -> InstanceModel:
        """Create an instance from a caller-supplied config, running no inference."""
        if request.source_file is None:
            raise InvalidRequestError(
                "create_confirmed requires source_file; it accepts no draft, "
                "sample-only source."
            )
        instance = self._create_source_instance(request)
        instance.confirm(_with_columns(confirmed_config))
        self._repository.save(instance)
        self._notify(instance)
        return instance

    def confirm(
        self,
        instance_id: UUID,
        confirmed_config: InstanceConfig,
        source_file: str | None = None,
    ) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        if instance.is_draft:
            if source_file is None:
                raise InvalidRequestError(
                    f"instance {instance_id} is a draft; confirm must supply source_file"
                )
            instance.attach_source(source_file)
            source = SourceRef(
                source_file=instance.source_file,
                source_file_name=instance.source_file_name,
                source_type=instance.source_type,
                source_file_format=instance.source_file_format,
            )
            validate_source_path(source)
            validate_file_format(source)
        instance.confirm(_with_columns(confirmed_config))
        self._repository.save(instance)
        self._notify(instance)
        return instance

    def _create_source_instance(self, request: SuggestionInput) -> InstanceModel:
        """Validate a source and open a pending instance over it.

        A draft (sample-only, no source_file yet) has nothing to validate against
        storage; validation runs again once a real source_file is attached at confirm.
        """
        if request.source_file is not None:
            validate_source_path(request)
            validate_file_format(request)
        instance = InstanceModel.create(
            source_file=request.source_file,
            source_file_name=request.source_file_name,
            source_type=request.source_type,
            source_file_format=request.source_file_format,
            source_checksum=request.source_checksum,
            layout_method=request.layout_method,
            typing_method=request.typing_method,
            extended_type_detection=request.extended_type_detection,
        )
        instance.webhook_url = request.webhook_url
        return instance

    @contextmanager
    def _terminal_on_error(self, instance: InstanceModel) -> Iterator[None]:
        """Guarantee a phase never leaves an instance frozen in an in-flight status.

        Any exception persists FAILED with its cause, notifies the webhook, and re-raises.
        """
        try:
            yield
        except Exception as exc:
            instance.fail(f"{type(exc).__name__}: {exc}")
            self._repository.save(instance)
            self._notify(instance)
            raise

    def _advance(self, instance: InstanceModel, status: InstanceStatus) -> None:
        instance.begin_phase(status)
        self._repository.save(instance)
        self._notify(instance)

    def profile(self, instance_id: UUID) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        # The precondition is a confirmed config, not a particular status: a retry
        # re-enters from whatever state the failed attempt left behind.
        confirmed = instance.confirmed_config
        if confirmed is None:
            raise InvalidStateError("instance must be CONFIRMED before profile")

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
        instance.record_issues("profiling", profiling_output.issues)
        instance.timings.profile_ended_at = datetime.now(UTC)
        self._repository.save(instance)
        self._notify(instance)
        return instance

    def normalize(self, instance_id: UUID) -> InstanceModel:
        instance = self._repository.get_required(instance_id)
        # As in profile(): the precondition is the output of the prior phase, not a
        # status, so a retry can re-enter from whatever the failed attempt left.
        profiling_output = instance.profiling_output
        confirmed = instance.confirmed_config
        if profiling_output is None or confirmed is None:
            raise InvalidStateError("instance must be PROFILED before normalize")

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
                issues=instance.issues,
                column_stats=profiling_output.column_stats,
                output_root=settings.conversion_output_dir,
                run_id=str(instance_id),
                persisted_db_path=db_cache_path,
            )
        db_cache_path.unlink(missing_ok=True)
        instance.set_normalization_output(
            result,
            thresholds=confirmed.operation_config.decision_thresholds,
        )
        instance.timings.convert_ended_at = datetime.now(UTC)
        self._repository.save(instance)
        self._notify(instance)
        return instance
