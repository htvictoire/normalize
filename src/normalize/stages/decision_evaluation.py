"""Decision evaluation stage."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter

from normalize.core.domain import IssueSeverity, NormalizationIssue, RunStatus
from normalize.stages.base import Stage


@dataclass(frozen=True)
class DecisionPolicy:
    """Explicit score thresholds used to derive terminal run status."""

    ready_threshold: Decimal
    warning_threshold: Decimal

    @classmethod
    def from_inputs(cls, *, ready_threshold: float, warning_threshold: float) -> DecisionPolicy:
        ready = Decimal(str(ready_threshold))
        warning = Decimal(str(warning_threshold))
        if warning < Decimal("0") or ready > Decimal("100"):
            raise ValueError("decision thresholds must satisfy 0 <= warning <= ready <= 100")
        if warning > ready:
            raise ValueError("decision thresholds must satisfy 0 <= warning <= ready <= 100")
        return cls(ready_threshold=ready, warning_threshold=warning)


class DecisionEvaluationStage(Stage):
    """
    Decide run status from quality score and blocking issues.

    Decision rules:
    - any ERROR issue => BLOCKED
    - quality >= ready_threshold => READY
    - quality >= warning_threshold => READY_WITH_WARNINGS
    - quality < warning_threshold => BLOCKED
    """

    def __init__(self, *, policy: DecisionPolicy) -> None:
        super().__init__()
        self._policy = policy

    def execute(
        self,
        quality_score: Decimal | float,
        issues: Iterable[NormalizationIssue] = (),
    ) -> RunStatus:
        start_time = perf_counter()
        if any(issue.severity is IssueSeverity.ERROR for issue in issues):
            status = RunStatus.BLOCKED
        else:
            score = Decimal(str(quality_score))
            if score >= self._policy.ready_threshold:
                status = RunStatus.READY
            elif score >= self._policy.warning_threshold:
                status = RunStatus.READY_WITH_WARNINGS
            else:
                status = RunStatus.BLOCKED

        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "quality_score": float(quality_score),
            "status": status.value,
            "ready_threshold": float(self._policy.ready_threshold),
            "warning_threshold": float(self._policy.warning_threshold),
        }
        return status
