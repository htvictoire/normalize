"""Serialization helpers for persistence of normalization instances."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shared.models.instance import InstanceModel
from shared.models.instance_config import InstanceConfig
from shared.models.normalization import NormalizationOutput
from shared.models.profiling import ProfilingOutput
from shared.models.suggestion import SuggestionDisplay


def instance_to_record(instance: InstanceModel) -> dict[str, Any]:
    """Serialize one instance to a column-mapped record."""
    return {
        "id": str(instance.id),
        "tenant_id": instance.tenant_id,
        "status": instance.status,
        "source_file": instance.source_file,
        "source_file_name": instance.source_file_name,
        "source_file_format": instance.source_file_format,
        "source_type": instance.source_type,
        "source_checksum": instance.source_checksum,
        "suggested_config": (
            instance.suggested_config.model_dump(mode="json")
            if instance.suggested_config is not None
            else None
        ),
        "suggestion_display": (
            instance.suggestion_display.model_dump(mode="json")
            if instance.suggestion_display is not None
            else None
        ),
        "confirmed_config": (
            instance.confirmed_config.model_dump(mode="json")
            if instance.confirmed_config is not None
            else None
        ),
        "profiling_output": (
            instance.profiling_output.model_dump(mode="json")
            if instance.profiling_output is not None
            else None
        ),
        "normalization_output": (
            instance.normalization_output.model_dump(mode="json")
            if instance.normalization_output is not None
            else None
        ),
    }


def record_to_instance(record: Mapping[str, Any]) -> InstanceModel:
    """Deserialize a column-mapped record into a strict instance."""
    return InstanceModel(
        id=record["id"],
        tenant_id=record["tenant_id"],
        status=record["status"],
        source_file=record["source_file"],
        source_file_name=record["source_file_name"],
        source_file_format=record["source_file_format"],
        source_type=record["source_type"],
        source_checksum=record["source_checksum"],
        suggested_config=(
            InstanceConfig.model_validate(record["suggested_config"])
            if record.get("suggested_config") is not None
            else None
        ),
        suggestion_display=(
            SuggestionDisplay.model_validate(record["suggestion_display"])
            if record.get("suggestion_display") is not None
            else None
        ),
        confirmed_config=(
            InstanceConfig.model_validate(record["confirmed_config"])
            if record.get("confirmed_config") is not None
            else None
        ),
        profiling_output=(
            ProfilingOutput.model_validate(record["profiling_output"])
            if record.get("profiling_output") is not None
            else None
        ),
        normalization_output=(
            NormalizationOutput.model_validate(record["normalization_output"])
            if record.get("normalization_output") is not None
            else None
        ),
    )
