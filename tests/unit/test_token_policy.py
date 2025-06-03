import pytest

from normalize.core.token_policy import TokenPolicy


def test_token_policy_requires_explicit_arrays() -> None:
    with pytest.raises(ValueError, match="MISSING_NULL_TOKENS"):
        TokenPolicy.from_user_inputs(
            null_tokens=None,
            boolean_true_tokens=["true"],
            boolean_false_tokens=["false"],
        )
    with pytest.raises(ValueError, match="MISSING_BOOLEAN_TRUE_TOKENS"):
        TokenPolicy.from_user_inputs(
            null_tokens=["null"],
            boolean_true_tokens=None,
            boolean_false_tokens=["false"],
        )
    with pytest.raises(ValueError, match="MISSING_BOOLEAN_FALSE_TOKENS"):
        TokenPolicy.from_user_inputs(
            null_tokens=["null"],
            boolean_true_tokens=["true"],
            boolean_false_tokens=None,
        )


def test_token_policy_rejects_overlapping_boolean_tokens() -> None:
    with pytest.raises(ValueError, match="BOOLEAN_TOKEN_CONFLICT"):
        TokenPolicy.from_user_inputs(
            null_tokens=["null"],
            boolean_true_tokens=["yes"],
            boolean_false_tokens=["yes"],
        )


def test_token_policy_rejects_null_boolean_overlap() -> None:
    with pytest.raises(ValueError, match="NULL_BOOLEAN_TOKEN_CONFLICT"):
        TokenPolicy.from_user_inputs(
            null_tokens=["null", "yes"],
            boolean_true_tokens=["yes"],
            boolean_false_tokens=["no"],
        )


def test_token_policy_normalizes_and_sorts_tokens() -> None:
    policy = TokenPolicy.from_user_inputs(
        null_tokens=[" NULL ", "n/a", ""],
        boolean_true_tokens=["Yes", "TRUE"],
        boolean_false_tokens=["No", "FALSE"],
    )
    assert policy.null_tokens == ("n/a", "null")
    assert policy.boolean_true_tokens == ("true", "yes")
    assert policy.boolean_false_tokens == ("false", "no")
    assert policy.boolean_tokens == ("false", "no", "true", "yes")
