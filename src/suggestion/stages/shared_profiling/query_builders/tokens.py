"""Token rendering helpers for profile query builders."""

from __future__ import annotations

from collections.abc import Sequence

from suggestion.stages.shared_profiling.sql_helpers import quote_string


def token_in_clause(tokens: Sequence[str]) -> str | None:
    """Render normalized tokens into SQL IN-clause content."""
    if not tokens:
        return None
    return ", ".join(quote_string(token) for token in tokens)
