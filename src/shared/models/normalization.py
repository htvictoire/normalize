"""Normalization-phase output models shared between the normalize pipeline and app layers."""

from __future__ import annotations

from pydantic import Field

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
    """Post-transform quality metrics computed by conversion.quality_metrics.

    An output NULL has two causes that mean opposite things: the source had no
    value, or the source had a value and we lost it. Only the second is a defect,
    so only the second feeds the score. `_parse_issues` tells them apart per cell.
    """

    row_count: int
    total_cells: int
    total_nullish_cells: int  # every output NULL: original nulls + parse failures
    total_original_null_cells: int  # source had no value; not a defect
    total_parse_error_cells: int  # source had a value and we lost it; a defect
    total_attempted_cells: int  # cells that carried a value to parse
    parse_success_ratio: float  # fidelity: of what was attempted, what survived
    completeness_ratio: float  # source density; reported, not scored
    quality_score: str = Field(
        description=(
            "Parse-fidelity score in [0, 100], a decimal serialized as a string "
            '(e.g. "94.50"): the share of attempted cells whose values survived '
            "parsing under the confirmed config. Not a semantic-correctness "
            "measure — a value read under a wrong declared convention (day/month "
            "order, CR/DR polarity) parses cleanly and scores 100. Review the "
            "emitted issues alongside the score."
        )
    )
    worst_column_score: str  # score of the least faithful column
    column_null_counts: dict[str, int]
    column_parse_error_counts: dict[str, int]
    column_parse_success_ratios: dict[str, float]


class NormalizationOutput(MainModel):
    """Normalization-phase terminal output stored on InstanceModel."""

    quality_output: QualityOutput
    artifacts: ArtifactPaths