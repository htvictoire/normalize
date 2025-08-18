"""Profiling phase application service."""

from __future__ import annotations

from pathlib import Path

from profiling.pipeline import run_profiling
from shared.models.column import ColumnConfig
from shared.models.operation import OperationConfig, SourceFormatConfig
from shared.models.profiling import ProfilingOutput


class ProfilingService:
    """Run mandatory full-dataset profiling phase from confirmed config."""

    def profile(
        self,
        *,
        file_path: str | Path,
        source_format: SourceFormatConfig,
        confirmed_column_config: dict[str, ColumnConfig],
        operation_config: OperationConfig,
    ) -> ProfilingOutput:
        """Execute full-dataset profiling and return profiling output only."""
        return run_profiling(
            file_path=file_path,
            source_format=source_format,
            column_config=confirmed_column_config,
            operation_config=operation_config,
        )
