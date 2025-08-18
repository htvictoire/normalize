"""Run-instance lifecycle models."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from shared.models.base import MainModel
from shared.models.confirmation import ConfirmedConfig
from shared.models.normalization import NormalizationOutput
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
    source_r2_url: str
    source_checksum: str | None
    suggested_config: SuggestionOutput | None = None
    confirmed_config: ConfirmedConfig | None = None
    profiling_output: ProfilingOutput | None = None
    normalization_output: NormalizationOutput | None = None

    @classmethod
    def create(
        cls,
        *,
        source_path: str | Path,
        source_file_name: str | None = None,
        tenant_id: str = "default",
        instance_id: UUID | None = None,
    ) -> InstanceModel:
        """Create a new pending instance from one source file path."""
        path = Path(source_path)
        return cls(
            id=instance_id or uuid4(),
            tenant_id=tenant_id,
            status=InstanceStatus.PENDING,
            source_file_name=path.name if source_file_name is None else source_file_name,
            source_r2_url=str(path),
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
