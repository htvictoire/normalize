from decimal import Decimal

import pytest

from normalize.core.quality import compute_quality_score


def test_quality_score_ready_boundary() -> None:
    score = compute_quality_score(1.0, 1.0)
    assert score == Decimal("100.00")


def test_quality_score_ready_with_warnings_range() -> None:
    score = compute_quality_score(0.9, 0.9)
    assert score == Decimal("91.000")


def test_quality_score_blocked_range() -> None:
    score = compute_quality_score(0.5, 0.5)
    assert score == Decimal("55.000")


def test_quality_score_rejects_invalid_ratio() -> None:
    with pytest.raises(ValueError, match="ratio must be between 0 and 1"):
        compute_quality_score(1.1, 0.5)


def test_quality_score_applies_pattern_consistency_weight() -> None:
    score = compute_quality_score(1.0, 1.0, pattern_consistency_ratio=0.8)
    assert score == Decimal("98.000")
