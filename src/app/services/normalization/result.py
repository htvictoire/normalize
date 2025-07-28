"""Normalization-phase return payload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.instance import InstanceModel


@dataclass(frozen=True)
class NormalizationResult:
    """Normalization-phase return payload."""

    instance: InstanceModel
    status: str
    quality_score: float
    issues: list[dict[str, Any]]
    fingerprint: str
    artifacts: dict[str, str] | None
    stage_metrics: dict[str, float]
