"""Profiling phase application service."""

from __future__ import annotations

from pathlib import Path

from shared.db.duckdb import DuckDBManager, resolve_db_path
from shared.ingestion import cleanup_ingestion_setup, resolve_ingestion_setup
from shared.models.instance_config import InstanceConfig
from shared.models.profiling import ProfilingOutput
from shared.models.source import SourceRef

from profiling import run_profiling


class ProfilingService:
    """Run mandatory full-dataset profiling phase from confirmed config."""

    def profile(
        self,
        source: SourceRef,
        source_checksum: str,
        confirmed_config: InstanceConfig,
        persisted_db_path: Path,
    ) -> ProfilingOutput:
        setup = resolve_ingestion_setup(source, confirmed_config.source_format)
        try:
            with DuckDBManager(database=resolve_db_path(str(persisted_db_path))) as conn:
                return run_profiling(conn, setup, source_checksum, confirmed_config)
        finally:
            cleanup_ingestion_setup(setup)
