"""
Strict token-policy contract for null and boolean interpretation.

This module centralizes token normalization and validation so all stages
(type inference, cell normalization, quality metrics) execute with one
deterministic policy and never rely on implicit defaults.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenPolicy:
    """
    Normalized token policy used by stages 4-6.

    Values are lowercase and trimmed. Empty-string null token is accepted as
    input but omitted from `null_tokens` because blank values are already
    treated as null by `NULLIF(TRIM(value), '')`.
    """

    null_tokens: tuple[str, ...]
    boolean_true_tokens: tuple[str, ...]
    boolean_false_tokens: tuple[str, ...]

    @property
    def boolean_tokens(self) -> tuple[str, ...]:
        """All normalized boolean tokens, sorted deterministically."""
        return tuple(sorted(set(self.boolean_true_tokens) | set(self.boolean_false_tokens)))

    @classmethod
    def from_user_inputs(
        cls,
        *,
        null_tokens: Sequence[str] | None,
        boolean_true_tokens: Sequence[str] | None,
        boolean_false_tokens: Sequence[str] | None,
    ) -> TokenPolicy:
        """
        Build validated token policy from explicit user-provided arrays.

        Validation guarantees:
        - all arrays are explicitly provided (no implicit defaults),
        - boolean true/false arrays are non-empty,
        - boolean true/false tokens do not overlap,
        - null tokens do not overlap with boolean tokens.
        """
        if null_tokens is None:
            raise ValueError("MISSING_NULL_TOKENS")
        if boolean_true_tokens is None:
            raise ValueError("MISSING_BOOLEAN_TRUE_TOKENS")
        if boolean_false_tokens is None:
            raise ValueError("MISSING_BOOLEAN_FALSE_TOKENS")

        normalized_null = _normalize_tokens(null_tokens, allow_empty=True, empty_error_code=None)
        normalized_true = _normalize_tokens(
            boolean_true_tokens,
            allow_empty=False,
            empty_error_code="EMPTY_BOOLEAN_TRUE_TOKENS",
        )
        normalized_false = _normalize_tokens(
            boolean_false_tokens,
            allow_empty=False,
            empty_error_code="EMPTY_BOOLEAN_FALSE_TOKENS",
        )

        overlap_true_false = set(normalized_true) & set(normalized_false)
        if overlap_true_false:
            joined = ",".join(sorted(overlap_true_false))
            raise ValueError(f"BOOLEAN_TOKEN_CONFLICT:{joined}")

        overlap_null_boolean = set(normalized_null) & (set(normalized_true) | set(normalized_false))
        if overlap_null_boolean:
            joined = ",".join(sorted(overlap_null_boolean))
            raise ValueError(f"NULL_BOOLEAN_TOKEN_CONFLICT:{joined}")

        return cls(
            null_tokens=normalized_null,
            boolean_true_tokens=normalized_true,
            boolean_false_tokens=normalized_false,
        )


def _normalize_tokens(
    values: Sequence[str],
    *,
    allow_empty: bool,
    empty_error_code: str | None,
) -> tuple[str, ...]:
    """Normalize raw user tokens to a sorted, unique tuple."""
    normalized: set[str] = set()
    for raw in values:
        value = raw.strip().lower()
        if value == "":
            if allow_empty:
                continue
            raise ValueError(empty_error_code or "EMPTY_TOKEN")
        normalized.add(value)

    if not normalized and empty_error_code is not None:
        raise ValueError(empty_error_code)
    return tuple(sorted(normalized))
