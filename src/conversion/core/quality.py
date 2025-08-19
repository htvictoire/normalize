"""Post-transform quality score computation."""

from __future__ import annotations

from decimal import Decimal

HUNDRED = Decimal("100")


def compute_quality_score(
    parse_success_ratio: float,
    completeness_ratio: float,
) -> Decimal:
    """
    Compute weighted quality score using deterministic Decimal arithmetic.

    Score formula (post-transform factors only):
      0.50 * parse_success_ratio
      0.50 * completeness_ratio

    Returns a value in [0, 100].
    """
    parse_success = _ratio_decimal(parse_success_ratio)
    completeness = _ratio_decimal(completeness_ratio)
    return (Decimal("0.50") * parse_success + Decimal("0.50") * completeness) * HUNDRED


def _ratio_decimal(value: float) -> Decimal:
    ratio = Decimal(str(value))
    if ratio < Decimal("0") or ratio > Decimal("1"):
        raise ValueError(f"ratio must be between 0 and 1, got {value}")
    return ratio
