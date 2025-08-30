import pytest

from conversion.core.token_policy import TokenPolicy


def test_token_policy_requires_null_tokens() -> None:
    with pytest.raises(ValueError, match="MISSING_NULL_TOKENS"):
        TokenPolicy.from_user_inputs(null_tokens=None)


def test_token_policy_normalizes_and_sorts_null_tokens() -> None:
    policy = TokenPolicy.from_user_inputs(null_tokens=[" NULL ", "n/a", ""])
    assert policy.null_tokens == ("n/a", "null")


def test_token_policy_allows_empty_null_tokens_list() -> None:
    policy = TokenPolicy.from_user_inputs(null_tokens=[])
    assert policy.null_tokens == ()
