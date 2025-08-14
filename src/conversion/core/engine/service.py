"""Conversion engine service entrypoint."""

from __future__ import annotations

from pathlib import Path

from conversion.core.engine.config import EngineConfig
from conversion.core.engine.pipeline import run_pipeline
from shared.models.normalization import NormalizationOutput
from shared.settings import get_settings


class ConversionEngine:
    """Execute the implemented stage pipeline with PROFILE/APPLY modes."""

    def __init__(self) -> None:
        settings = get_settings()
        self._duckdb_memory_limit = settings.duckdb_memory_limit

    def run(
        self,
        csv_path: str | Path,
        output_dir: str | Path,
        config: EngineConfig,
        mode: str = "APPLY",
    ) -> NormalizationOutput:
        """
        Run pipeline stages and optionally materialize artifacts.

        Returns:
        - `status`
        - `fingerprint`
        - `artifacts` (APPLY only; None for PROFILE)
        """
        run_mode = mode.upper()
        effective = config

        source_csv = Path(csv_path)
        if not source_csv.is_absolute():
            source_csv = Path.cwd() / source_csv
        if not source_csv.exists():
            raise FileNotFoundError(f"CSV file not found: {source_csv}")

        output_root = Path(output_dir)
        if not output_root.is_absolute():
            output_root = Path.cwd() / output_root
        output_root.mkdir(parents=True, exist_ok=True)

        return run_pipeline(
            source_csv=source_csv,
            output_root=output_root,
            effective=effective,
            run_mode=run_mode,
            duckdb_memory_limit=self._duckdb_memory_limit,
        )
