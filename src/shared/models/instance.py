"""Instance models — status and lifecycle model for a normalization run."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from shared.models.base import MainModel
from shared.models.instance_config import InstanceConfig
from shared.models.issues import IssueSeverity, NormalizationIssue
from shared.models.normalization import NormalizationOutput
from shared.models.operation import (
    DecisionThresholds,
    FileFormat,
    FileSource,
    SuggestionMethod,
)
from shared.models.profiling import ProfilingOutput
from shared.models.suggestion import SuggestionConfidence, SuggestionDisplay


class StageTimings(MainModel):
    """Wall-clock timestamps and duration estimate for each pipeline stage."""

    suggest_started_at: datetime | None = None
    suggest_ended_at: datetime | None = None
    profile_started_at: datetime | None = None
    profile_ended_at: datetime | None = None
    convert_started_at: datetime | None = None
    convert_ended_at: datetime | None = None
    estimated_pipeline_seconds: int | None = None


class InstanceStatus(StrEnum):
    """Lifecycle status for suggest->confirm->profile->normalize orchestration."""

    PENDING = "PENDING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    PROFILING = "PROFILING"
    PROFILED = "PROFILED"
    NORMALIZING = "NORMALIZING"
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


def evaluate_decision(
    quality_score: Decimal,
    worst_column_score: Decimal,
    issues: Iterable[NormalizationIssue],
    thresholds: DecisionThresholds,
) -> InstanceStatus:
    """Derive the terminal status of a completed run from its scores and issues.

    BLOCKED is a verdict on the data; FAILED means the pipeline itself crashed.
    Consumers gate on this status, so the two must never be conflated.

    Thresholds apply to the worse of the table score and the worst single column:
    a mean hides an annihilated column, and a run is only as trustworthy as its
    least trustworthy column.
    """
    effective_score = min(quality_score, worst_column_score)
    severities = {issue.severity for issue in issues}
    if IssueSeverity.ERROR in severities:
        return InstanceStatus.BLOCKED
    if effective_score < Decimal(str(thresholds.warning)):
        return InstanceStatus.BLOCKED
    if effective_score < Decimal(str(thresholds.ready)):
        return InstanceStatus.READY_WITH_WARNINGS
    if IssueSeverity.WARNING in severities:
        # Warnings rest on evidence the score cannot see (mixed currency,
        # duplicate identifiers), so a clean score does not overrule them.
        return InstanceStatus.READY_WITH_WARNINGS
    return InstanceStatus.READY


class InstanceModel(MainModel):
    """Single run instance used as suggest -> normalize handoff."""

    instance_id: UUID
    tenant_id: str
    status: InstanceStatus
    source_file_name: str
    source_file_format: FileFormat
    source_file: str
    source_type: FileSource
    source_checksum: str
    suggestion_method: SuggestionMethod
    extended_type_detection: bool
    webhook_url: str | None = None
    suggested_config: InstanceConfig | None = None
    suggestion_display: SuggestionDisplay | None = None
    suggestion_confidence: SuggestionConfidence | None = None
    confirmed_config: InstanceConfig | None = None
    profiling_output: ProfilingOutput | None = None
    normalization_output: NormalizationOutput | None = None
    failure_reason: str | None = None
    timings: StageTimings = Field(default_factory=StageTimings)

    @classmethod
    def create(
        cls,
        source_file: str,
        source_file_name: str,
        source_type: FileSource,
        source_file_format: FileFormat,
        source_checksum: str,
        suggestion_method: SuggestionMethod,
        extended_type_detection: bool,
        tenant_id: str = "default",
        instance_id: UUID | None = None,
    ) -> InstanceModel:
        """Create a new pending instance."""
        return cls(
            instance_id=instance_id or uuid4(),
            tenant_id=tenant_id,
            status=InstanceStatus.PENDING,
            source_file_name=source_file_name,
            source_file_format=source_file_format,
            source_file=source_file,
            source_type=source_type,
            source_checksum=source_checksum,
            suggestion_method=suggestion_method,
            extended_type_detection=extended_type_detection,
        )

    def set_suggestion_output(
        self,
        suggested_config: InstanceConfig,
        confidence: SuggestionConfidence,
        display: SuggestionDisplay,
    ) -> None:
        """Store suggestion results and move status to awaiting confirmation."""
        self.suggested_config = suggested_config
        self.suggestion_confidence = confidence
        self.suggestion_display = display
        self.status = InstanceStatus.AWAITING_CONFIRMATION

    def confirm(self, confirmed_config: InstanceConfig) -> None:
        """Persist confirmed config and mark instance ready to profile."""
        self.confirmed_config = confirmed_config
        self.status = InstanceStatus.CONFIRMED

    def set_profiling_output(self, profiling_output: ProfilingOutput) -> None:
        """Store full-dataset profiling output and advance status to PROFILED."""
        self.profiling_output = profiling_output
        self.status = InstanceStatus.PROFILED

    def set_normalization_output(
        self,
        normalization_output: NormalizationOutput,
        issues: Iterable[NormalizationIssue],
        thresholds: DecisionThresholds,
    ) -> None:
        """Store normalization output and advance to the decided terminal state."""
        self.normalization_output = normalization_output
        quality = normalization_output.quality_output
        self.status = evaluate_decision(
            quality_score=Decimal(quality.quality_score),
            worst_column_score=Decimal(quality.worst_column_score),
            issues=issues,
            thresholds=thresholds,
        )

    def begin_phase(self, status: InstanceStatus) -> None:
        """Enter an in-flight phase, discarding any failure left by a previous attempt."""
        self.failure_reason = None
        self.status = status

    def fail(self, reason: str) -> None:
        """Terminate as FAILED: the pipeline crashed, recording what threw.

        Not BLOCKED — BLOCKED is a verdict on the data, this is a bug to debug.
        """
        self.failure_reason = reason
        self.status = InstanceStatus.FAILED
