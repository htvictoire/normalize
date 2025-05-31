"""Type inference stage package."""

from normalize.stages.type_inference.contracts import SUPPORTED_INFERRED_TYPES
from normalize.stages.type_inference.stage import TypeInferenceStage

__all__ = ["TypeInferenceStage", "SUPPORTED_INFERRED_TYPES"]
