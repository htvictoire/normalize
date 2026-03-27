"""Manifest payload creation and write helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from shared.models.issues import IssueSeverity, NormalizationIssue
from shared.models.normalization import QualityOutput, SourceChecksums


def build_issue_summary(issues: Sequence[NormalizationIssue]) -> dict[str, Any]:
    """Aggregate issue counts by severity."""
    by_severity: dict[str, int] = {s.value: 0 for s in IssueSeverity}
    for issue in issues:
        by_severity[issue.severity.value] += 1
    return {"total_count": len(issues), "by_severity": by_severity}


def build_manifest_payload(
    fingerprint: str,
    source_checksums: SourceChecksums,
    stage_metrics: Mapping[str, Mapping[str, Any]],
    quality_output: QualityOutput,
    issues: Sequence[NormalizationIssue],
    normalized_checksum: str,
    trace_checksum: str,
    effective_config: Mapping[str, Any],
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
        "source_checksums": {"source_file": source_checksums.source_file},
        "stage_metrics": dict(stage_metrics),
        "quality_summary": quality_output.model_dump(),
        "issue_summary": build_issue_summary(issues),
        "artifact_checksums": {
            "normalized_parquet": normalized_checksum,
            "trace_parquet": trace_checksum,
        },
        "replay_instructions": {
            "effective_config": dict(effective_config),
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
