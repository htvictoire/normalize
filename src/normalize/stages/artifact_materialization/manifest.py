"""Manifest payload creation and write helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def build_issue_summary(issues: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate issue counts by severity."""
    by_severity: dict[str, int] = {}
    for issue in issues:
        severity = str(issue.get("severity", "UNKNOWN")).upper()
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return {"total_count": len(issues), "by_severity": by_severity}


def build_manifest_payload(
    *,
    fingerprint: str,
    source_checksums: Mapping[str, str] | None,
    stage_metrics: Mapping[str, Mapping[str, Any]] | None,
    quality_summary: Mapping[str, Any] | None,
    issue_summary: Mapping[str, Any],
    normalized_checksum: str,
    trace_checksum: str,
    effective_config: Mapping[str, Any] | None,
    rules_version: str,
    duckdb_version: str,
    normalized_path: Path,
    trace_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Create manifest payload dict."""
    artifact_base = manifest_path.parent
    normalized_rel = _relative_path(normalized_path, artifact_base)
    trace_rel = _relative_path(trace_path, artifact_base)
    manifest_rel = _relative_path(manifest_path, artifact_base)
    return {
        "fingerprint": fingerprint,
        "source_checksums": dict(source_checksums or {}),
        "stage_metrics": dict(stage_metrics or {}),
        "quality_summary": dict(quality_summary or {}),
        "issue_summary": dict(issue_summary),
        "artifact_checksums": {
            "normalized_parquet": normalized_checksum,
            "trace_parquet": trace_checksum,
        },
        "replay_instructions": {
            "effective_config": dict(effective_config or {}),
            "rules_version": rules_version,
            "duckdb_version": duckdb_version,
        },
        "artifacts": {
            "normalized_parquet": normalized_rel,
            "trace_parquet": trace_rel,
            "manifest_json": manifest_rel,
        },
    }


def write_manifest(manifest_path: Path, payload: Mapping[str, Any]) -> None:
    """Write manifest JSON deterministically."""
    manifest_path.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )


def _relative_path(path: Path, base_dir: Path) -> str:
    """Return a portable path relative to base_dir."""
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(path.name)
    return relative.as_posix()
