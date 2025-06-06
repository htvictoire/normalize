"""Naming helpers for cell normalization internals."""

from __future__ import annotations


def issue_alias(column_name: str) -> str:
    """Return deterministic temporary issue-column alias for one data column."""
    return f"__issue__{column_name}"
