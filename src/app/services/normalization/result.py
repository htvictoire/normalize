"""Normalization-phase return payload."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.instance import InstanceModel


@dataclass(frozen=True)
class NormalizationResult:
    """Normalization-phase return payload."""

    instance: InstanceModel
    status: str
    fingerprint: str
    artifacts: dict[str, str] | None
