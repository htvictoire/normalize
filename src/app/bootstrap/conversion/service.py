"""Conversion-phase application service."""

from __future__ import annotations

from pathlib import Path

from app.bootstrap.conversion.execution import (
    ConversionExecutionOutput,
    execute_conversion,
)
from shared.models.column import ColumnConfig
from shared.models.issues import IssueSeverity, NormalizationIssue
from shared.models.operation import OperationConfig, SourceFormat
from shared.models.source import SourceRef
from shared.settings import get_settings


class ConversionService:
    """Run conversion using confirmed config and profiling outputs."""

    def convert(
        self,
        *,
        source: SourceRef,
        source_format: SourceFormat,
        source_checksum: str,
        confirmed_column_config: dict[str, ColumnConfig],
        operation_config: OperationConfig,
        profiling_issues: list[NormalizationIssue],
        output_root: Path,
    ) -> ConversionExecutionOutput:
        """Execute conversion phase with explicit inputs only."""
        if any(issue.severity is IssueSeverity.ERROR for issue in profiling_issues):
            raise ValueError("instance has blocking profiling issues")

        settings = get_settings()

        return execute_conversion(
            source=source,
            source_format=source_format,
            source_checksum=source_checksum,
            confirmed_column_config=confirmed_column_config,
            operation_config=operation_config,
            profiling_issues=profiling_issues,
            output_root=output_root,
            duckdb_memory_limit=settings.duckdb_memory_limit,
        )
