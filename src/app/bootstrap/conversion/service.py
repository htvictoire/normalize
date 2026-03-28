"""Conversion-phase application service."""

from __future__ import annotations

from pathlib import Path

from shared.models.column import ColumnConfig
from shared.models.issues import NormalizationIssue
from shared.models.operation import OperationConfig, SourceFormat
from shared.models.source import SourceRef
from shared.settings import get_settings

from app.bootstrap.conversion.execution import (
    ConversionExecutionOutput,
    execute_conversion,
)


class ConversionService:
    """Run conversion using confirmed config and profiling outputs."""

    def convert(
        self,
        source: SourceRef,
        source_format: SourceFormat,
        source_checksum: str,
        confirmed_column_config: dict[str, ColumnConfig],
        operation_config: OperationConfig,
        profiling_issues: list[NormalizationIssue],
        output_root: str | Path,
        run_id: str | None,
        persisted_db_path: Path,
    ) -> ConversionExecutionOutput:
        """Execute conversion phase with explicit inputs only."""
        settings = get_settings()

        return execute_conversion(
            source=source,
            source_format=source_format,
            source_checksum=source_checksum,
            confirmed_column_config=confirmed_column_config,
            operation_config=operation_config,
            profiling_issues=profiling_issues,
            output_root=output_root,
            run_id=run_id,
            duckdb_memory_limit=settings.duckdb_memory_limit,
            persisted_db_path=persisted_db_path,
        )
