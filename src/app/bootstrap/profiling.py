"""Profiling phase application service."""

from __future__ import annotations

from pathlib import Path

from shared.models.instance_config import InstanceConfig
from shared.models.profiling import ProfilingOutput
from shared.models.source import SourceRef

from profiling import run_profiling


class ProfilingService:
    """Run mandatory full-dataset profiling phase from confirmed config."""

    def profile(
        self,
        *,
        source: SourceRef,
        source_checksum: str,
        confirmed_config: InstanceConfig,
        persisted_db_path: Path,
    ) -> ProfilingOutput:
        """Execute full-dataset profiling and return profiling output only."""
        return run_profiling(
            source,
            source_checksum=source_checksum,
            confirmed_config=confirmed_config,
            persisted_db_path=persisted_db_path,
        )
