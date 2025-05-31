"""Normalization engine service entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from normalize.config.settings import get_settings
from normalize.core.engine.config import EngineConfig
from normalize.core.engine.pipeline import run_pipeline
from normalize.stages.ingestion.contracts import HeaderMode


class NormalizationEngine:
    """Execute the implemented stage pipeline with PROFILE/APPLY modes."""

    def __init__(self) -> None:
        settings = get_settings()
        self._duckdb_memory_limit = settings.duckdb_memory_limit

    def run(
        self,
        csv_path: str | Path,
        output_dir: str | Path,
        config: EngineConfig | dict[str, Any],
        mode: str = "APPLY",
    ) -> dict[str, Any]:
        """
        Run pipeline stages and optionally materialize artifacts.

        Returns:
        - `status`
        - `quality_score`
        - `issues`
        - `fingerprint`
        - `artifacts` (APPLY only; None for PROFILE)
        - `stage_seconds`
        """
        run_mode = mode.upper()
        if run_mode not in {"PROFILE", "APPLY"}:
            raise ValueError("mode must be PROFILE or APPLY")

        effective = self._resolve_config(config)
        if effective.include_per_column_parse_error_counts and not effective.emit_parse_issues:
            raise ValueError(
                "include_per_column_parse_error_counts requires emit_parse_issues=True"
            )
        if effective.full_raw_row and not effective.emit_raw_row:
            raise ValueError("full_raw_row requires emit_raw_row=True")
        if effective.trace_mode not in {"full", "sparse"}:
            raise ValueError("trace_mode must be one of: full, sparse")

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

    def _resolve_config(self, config: EngineConfig | dict[str, Any]) -> EngineConfig:
        if isinstance(config, EngineConfig):
            return config
        if isinstance(config, dict):
            payload = dict(config)
            if isinstance(payload.get("header_mode"), str):
                payload["header_mode"] = HeaderMode(payload["header_mode"])
            return EngineConfig(**payload)
        raise TypeError("config must be EngineConfig or dict")
