"""Repository contract for normalization instances."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from shared.models.instance import InstanceModel


class NormalizationInstanceRepository(Protocol):
    """Persistence contract for run instances."""

    def save(self, instance: InstanceModel) -> InstanceModel:
        """Insert or update one instance."""

    def get(self, instance_id: UUID) -> InstanceModel | None:
        """Fetch one instance by id."""

    def get_required(self, instance_id: UUID) -> InstanceModel:
        """Fetch one instance or raise when it does not exist."""


class InMemoryNormalizationInstanceRepository:
    """In-memory repository implementation for local execution and tests."""

    def __init__(self) -> None:
        self._instances: dict[UUID, InstanceModel] = {}

    def save(self, instance: InstanceModel) -> InstanceModel:
        self._instances[instance.id] = instance
        return instance

    def get(self, instance_id: UUID) -> InstanceModel | None:
        instance = self._instances.get(instance_id)
        if instance is None:
            return None
        return instance.model_copy(deep=True)

    def get_required(self, instance_id: UUID) -> InstanceModel:
        instance = self._instances.get(instance_id)
        if instance is None:
            raise KeyError(f"instance not found: {instance_id}")
        return instance
