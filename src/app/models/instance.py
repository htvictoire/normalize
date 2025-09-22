"""Run-instance lifecycle models."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from shared.models.base import MainModel
from shared.models.confirmation import ConfirmedConfig
from shared.models.normalization import NormalizationOutput
from shared.models.operation import FileFormat, FileSource
from shared.models.profiling import ProfilingOutput
from shared.models.suggestion import SuggestionOutput


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


class InstanceModel(MainModel):
    """Single run instance used as suggest -> normalize handoff."""

    id: UUID
    tenant_id: str
    status: InstanceStatus
    source_file_name: str
    source_file_format: FileFormat
    source_file: str
    source_type: FileSource
    source_checksum: str | None
    suggested_config: SuggestionOutput | None = None
    confirmed_config: ConfirmedConfig | None = None
    profiling_output: ProfilingOutput | None = None
    normalization_output: NormalizationOutput | None = None

    @classmethod
    def create(
        cls,
        *,
        source_file: str,
        source_file_name: str,
        source_type: FileSource,
        source_file_format: FileFormat,
        tenant_id: str = "default",
        instance_id: UUID | None = None,
    ) -> InstanceModel:
        """Create a new pending instance."""
        return cls(
            id=instance_id or uuid4(),
            tenant_id=tenant_id,
            status=InstanceStatus.PENDING,
            source_file_name=source_file_name,
            source_file_format=source_file_format,
            source_file=source_file,
            source_type=source_type,
            source_checksum=None,
        )

    def set_suggestion_output(self, suggestion: SuggestionOutput) -> None:
        """Write suggestion output and move status to awaiting confirmation."""
        self.suggested_config = suggestion
        self.status = InstanceStatus.AWAITING_CONFIRMATION

    def confirm(self, confirmed_config: ConfirmedConfig) -> None:
        """Persist confirmed config and mark instance ready to profile."""
        self.confirmed_config = confirmed_config
        self.status = InstanceStatus.CONFIRMED

    def set_profiling_output(self, *, profiling_output: ProfilingOutput) -> None:
        """Store full-dataset profiling output and advance status to PROFILED."""
        self.profiling_output = profiling_output
        self.status = InstanceStatus.PROFILED

    def set_normalization_output(self, *, normalization_output: NormalizationOutput) -> None:
        """Store normalization output and advance status to terminal state."""
        self.normalization_output = normalization_output
        self.status = InstanceStatus.READY
