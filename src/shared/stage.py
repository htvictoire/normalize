"""Base abstraction for pipeline stages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Stage(ABC):
    """Minimal stage contract with in-memory issue and metric capture."""

    def __init__(self) -> None:
        self.issues: list[dict[str, Any]] = []
        self.metrics: dict[str, float | int | str] = {}

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the stage."""
