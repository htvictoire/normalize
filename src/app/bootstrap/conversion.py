"""Conversion-phase application service."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from shared.db.duckdb import DuckDBManager, resolve_db_path
from shared.models.column import ColumnConfig
from shared.models.issues import NormalizationIssue
from shared.models.normalization import NormalizationOutput
from shared.models.operation import OperationConfig
from shared.models.profiling import ColumnProfileStats
from shared.models.source import SourceRef
from shared.settings import get_settings

from conversion.artifacts import materialize_artifacts
from conversion.pipeline import run_conversion


class ConversionService:
    """Run conversion using confirmed config and profiling outputs."""

    def convert(
        self,
        source: SourceRef,
        source_checksum: str,
        confirmed_column_config: dict[str, ColumnConfig],
        operation_config: OperationConfig,
        profiling_issues: list[NormalizationIssue],
        column_stats: Mapping[str, ColumnProfileStats],
        output_root: str | Path,
        run_id: str,
        persisted_db_path: Path,
    ) -> NormalizationOutput:
        if not persisted_db_path.exists():
            raise FileNotFoundError(f"Profiling cache not found: {persisted_db_path}")

        settings = get_settings()
        with DuckDBManager(
            memory_limit=settings.duckdb_memory_limit,
            threads=settings.duckdb_threads,
            database=resolve_db_path(str(persisted_db_path)),
        ) as conn:
            result = run_conversion(
                conn,
                confirmed_column_config,
                operation_config,
                column_stats,
            )
            artifacts = materialize_artifacts(
                conn,
                output_dir=output_root,
                output_type=source.source_type,
                result=result,
                source_checksum=source_checksum,
                issues=profiling_issues,
                run_id=run_id,
                trace_mode=operation_config.trace_mode,
            )
            return NormalizationOutput(
                quality_output=result.quality_output,
                artifacts=artifacts,
            )
