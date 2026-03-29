"""Normalization-phase output models shared between the normalize pipeline and app layers."""

from __future__ import annotations

from shared.models.base import MainModel


class ArtifactPaths(MainModel):
    """Artifact locations written by normalization.

    For local sources these are filesystem paths.
    For S3 sources these are S3 keys.
    """

    normalized_parquet: str
    manifest_json: str
    trace_parquet: str


class QualityOutput(MainModel):
    """Post-transform quality metrics produced by QualityMetricsStage."""

    row_count: int
    total_cells: int
    total_nullish_cells: int
    total_parse_error_cells: int
    parse_success_ratio: float
    completeness_ratio: float
    quality_score: str  # Decimal serialized as string, e.g. "94.50"
    column_null_counts: dict[str, int]


class NormalizationOutput(MainModel):
    """Normalization-phase terminal output stored on InstanceModel."""

    quality_output: QualityOutput
    artifacts: ArtifactPaths