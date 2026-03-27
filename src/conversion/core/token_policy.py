"""
Strict token-policy contract for null interpretation.

This module centralizes null token normalization and validation so all stages
execute with one deterministic policy and never rely on implicit defaults.

Boolean tokens are per-column, stored on BooleanColumnConfig.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenPolicy:
    """
    Normalized null token policy used by stages 4-6.

    Values are lowercase and trimmed. Empty-string null token is accepted as
    input but omitted from `null_tokens` because blank values are already
    treated as null by `NULLIF(TRIM(value), '')`.
    """

    null_tokens: tuple[str, ...]

    @classmethod
    def from_user_inputs(
        cls,
        null_tokens: Sequence[str] | None,
    ) -> TokenPolicy:
        """Build a TokenPolicy from caller-supplied null tokens, rejecting None."""
        if null_tokens is None:
            raise ValueError("MISSING_NULL_TOKENS")

        normalized_null = _normalize_tokens(null_tokens, allow_empty=True, empty_error_code=None)
        return cls(null_tokens=normalized_null)


def _normalize_tokens(
    values: Sequence[str],
    allow_empty: bool,
    empty_error_code: str | None,
) -> tuple[str, ...]:
    """Normalize raw user tokens to a sorted, unique tuple."""
    normalized: set[str] = set()
    for raw in values:
        value = raw.strip().lower()
        if not value:
            if allow_empty:
                continue
            raise ValueError(empty_error_code or "EMPTY_TOKEN")
        normalized.add(value)

    if not normalized and empty_error_code is not None:
        raise ValueError(empty_error_code)
    return tuple(sorted(normalized))
