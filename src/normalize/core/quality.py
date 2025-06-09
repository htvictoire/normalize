"""Quality score computation."""

from __future__ import annotations

from decimal import Decimal

HUNDRED = Decimal("100")


def compute_quality_score(
    parse_success_ratio: float,
    completeness_ratio: float,
    *,
    pattern_consistency_ratio: float = 1.0,
    anomaly_ratio: float = 1.0,
    schema_stability_ratio: float = 1.0,
) -> Decimal:
    """
    Compute weighted quality score using deterministic Decimal arithmetic.

    Score formula:
    - 0.45 parse_success
    - 0.45 completeness
    - 0.10 pattern_consistency
    - 0.00 anomaly_ratio (stubbed)
    - 0.00 schema_stability (stubbed)
    """
    parse_success = _ratio_decimal(parse_success_ratio)
    completeness = _ratio_decimal(completeness_ratio)
    pattern_consistency = _ratio_decimal(pattern_consistency_ratio)
    anomaly = _ratio_decimal(anomaly_ratio)
    schema_stability = _ratio_decimal(schema_stability_ratio)

    score = (
        Decimal("0.45") * parse_success
        + Decimal("0.45") * completeness
        + Decimal("0.10") * pattern_consistency
        + Decimal("0.00") * anomaly
        + Decimal("0.00") * schema_stability
    ) * HUNDRED
    return score


def _ratio_decimal(value: float) -> Decimal:
    ratio = Decimal(str(value))
    if ratio < Decimal("0") or ratio > Decimal("1"):
        raise ValueError("ratio must be between 0 and 1")
    return ratio
