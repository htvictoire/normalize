"""Serialization helpers for persistence of normalization instances."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.instance import InstanceModel


def instance_to_record(instance: InstanceModel) -> dict[str, Any]:
    """Serialize one instance to a JSON-compatible record."""
    return instance.model_dump(mode="json")


def record_to_instance(record: Mapping[str, Any]) -> InstanceModel:
    """Deserialize one persisted record into a strict instance."""
    return InstanceModel.model_validate(record)
