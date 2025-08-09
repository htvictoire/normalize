"""Run-instance lifecycle models."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from profile.models import ProfileOutput
from uuid import UUID, uuid4

from pydantic import Field

from shared.models.base import MainModel
from shared.models.column import ColumnConfig
from shared.models.operation import OperationConfig, SourceFormatConfig
from shared.models.profiling import ProfilingStats


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


class NormalizationOutput(MainModel):
    """Normalization-phase terminal output."""

    fingerprint: str
    artifacts: dict[str, str] | None


class InstanceModel(MainModel):
    """Single run instance used as suggest -> normalize handoff."""

    id: UUID
    tenant_id: str
    status: InstanceStatus
    source_file_name: str
    source_r2_url: str
    source_checksum: str | None
    source_format: SourceFormatConfig
    column_labels: dict[str, str] = Field(default_factory=dict)
    suggested_column_config: dict[str, ColumnConfig] = Field(default_factory=dict)
    profiling_stats: ProfilingStats | None = None
    confirmed_column_config: dict[str, ColumnConfig] | None = None
    operation_config: OperationConfig | None = None
    profile_output: ProfileOutput | None = None
    normalization_output: NormalizationOutput | None = None

    @classmethod
    def create(
        cls,
        *,
        source_path: str | Path,
        source_file_name: str | None = None,
        source_format: SourceFormatConfig,
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
            source_format=source_format,
        )

    def set_suggestion_output(
        self,
        *,
        column_labels: Mapping[str, str],
        suggested_column_config: dict[str, ColumnConfig],
        profiling_stats: ProfilingStats,
    ) -> None:
        """Write suggestion output and move status to awaiting confirmation."""
        self.column_labels = {str(key): str(value) for key, value in column_labels.items()}
        self.suggested_column_config = suggested_column_config
        self.profiling_stats = profiling_stats
        self.status = InstanceStatus.AWAITING_CONFIRMATION

    def confirm(
        self,
        *,
        confirmed_column_config: dict[str, ColumnConfig],
        operation_config: OperationConfig,
    ) -> None:
        """Persist caller-confirmed config and mark instance ready to profile."""
        self.confirmed_column_config = dict(confirmed_column_config)
        self.operation_config = operation_config
        self.status = InstanceStatus.CONFIRMED

    def set_profile_output(self, *, profile_output: ProfileOutput) -> None:
        """Store full-dataset profile output and advance status to PROFILED."""
        self.profile_output = profile_output
        self.status = InstanceStatus.PROFILED
