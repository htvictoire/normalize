"""Conversion-phase application service."""

from __future__ import annotations

from pathlib import Path

from app.bootstrap.conversion.execution import (
    ConversionExecutionOutput,
    execute_conversion,
)
from shared.models.column import ColumnConfig
from shared.models.issues import IssueSeverity, NormalizationIssue
from shared.models.operation import OperationConfig, RunMode, SourceFormatConfig
from shared.settings import get_settings


class ConversionService:
    """Run conversion using confirmed config and profiling outputs."""

    def convert(
        self,
        *,
        file_path: str | Path,
        source_format: SourceFormatConfig,
        source_checksum: str,
        confirmed_column_config: dict[str, ColumnConfig],
        operation_config: OperationConfig,
        profiling_issues: list[NormalizationIssue],
        output_dir: str | Path,
        mode: RunMode = "APPLY",
        rules_version: str = "v1",
    ) -> ConversionExecutionOutput:
        """Execute conversion phase with explicit inputs only."""
        if any(issue.severity is IssueSeverity.ERROR for issue in profiling_issues):
            raise ValueError("instance has blocking profiling issues")

        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        settings = get_settings()

        return execute_conversion(
            source_csv=Path(file_path),
            source_format=source_format,
            source_checksum=source_checksum,
            confirmed_column_config=confirmed_column_config,
            operation_config=operation_config,
            profiling_issues=profiling_issues,
            output_root=output_root,
            run_mode=mode,
            rules_version=rules_version,
            duckdb_memory_limit=settings.duckdb_memory_limit,
        )
