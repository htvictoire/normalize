from decimal import Decimal

from normalize.core.domain import IssueSeverity, NormalizationIssue, RunStatus
from normalize.stages.decision_evaluation import DecisionEvaluationStage, DecisionPolicy


def test_decision_ready_at_95_and_above() -> None:
    stage = DecisionEvaluationStage(
        policy=DecisionPolicy.from_inputs(ready_threshold=95.0, warning_threshold=85.0)
    )
    assert stage.execute(Decimal("95")) == RunStatus.READY
    assert stage.execute(Decimal("100")) == RunStatus.READY


def test_decision_ready_with_warnings_between_85_and_95() -> None:
    stage = DecisionEvaluationStage(
        policy=DecisionPolicy.from_inputs(ready_threshold=95.0, warning_threshold=85.0)
    )
    assert stage.execute(Decimal("85")) == RunStatus.READY_WITH_WARNINGS
    assert stage.execute(Decimal("94.99")) == RunStatus.READY_WITH_WARNINGS


def test_decision_blocked_below_85() -> None:
    stage = DecisionEvaluationStage(
        policy=DecisionPolicy.from_inputs(ready_threshold=95.0, warning_threshold=85.0)
    )
    assert stage.execute(Decimal("84.99")) == RunStatus.BLOCKED


def test_decision_blocked_when_error_issue_exists() -> None:
    stage = DecisionEvaluationStage(
        policy=DecisionPolicy.from_inputs(ready_threshold=95.0, warning_threshold=85.0)
    )
    issues = [
        NormalizationIssue(
            code="BAD_THING",
            severity=IssueSeverity.ERROR,
            message="Blocking issue",
        )
    ]
    assert stage.execute(Decimal("99"), issues) == RunStatus.BLOCKED


def test_decision_supports_fully_configurable_thresholds() -> None:
    stage = DecisionEvaluationStage(
        policy=DecisionPolicy.from_inputs(ready_threshold=98.0, warning_threshold=90.0)
    )
    assert stage.execute(Decimal("98")) == RunStatus.READY
    assert stage.execute(Decimal("90")) == RunStatus.READY_WITH_WARNINGS
    assert stage.execute(Decimal("89.99")) == RunStatus.BLOCKED
