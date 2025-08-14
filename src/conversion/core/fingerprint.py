"""Deterministic run fingerprint helpers."""

from __future__ import annotations

import hashlib


def compute_fingerprint(
    source_checksum: str,
    config_json: str,
    rules_version: str,
    duckdb_version: str,
) -> str:
    """
    Compute deterministic SHA256 fingerprint from core replay inputs.

    The fingerprint is the SHA256 hex digest of concatenated input components.
    """
    payload = source_checksum + config_json + rules_version + duckdb_version
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
