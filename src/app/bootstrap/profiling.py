"""Profiling phase application service."""

from __future__ import annotations

from pathlib import Path

from profiling import run_profiling
from shared.models.column import ColumnConfig
from shared.models.operation import OperationConfig, SourceFormat
from shared.models.profiling import ProfilingOutput
from shared.models.source import SourceRef


class ProfilingService:
    """Run mandatory full-dataset profiling phase from confirmed config."""

    def profile(
        self,
        *,
        source: SourceRef,
        source_checksum: str,
        source_format: SourceFormat,
        confirmed_column_config: dict[str, ColumnConfig],
        operation_config: OperationConfig,
        persisted_db_path: Path,
    ) -> ProfilingOutput:
        """Execute full-dataset profiling and return profiling output only."""
        return run_profiling(
            source,
            source_checksum=source_checksum,
            source_format=source_format,
            column_config=confirmed_column_config,
            operation_config=operation_config,
            persisted_db_path=persisted_db_path,
        )
