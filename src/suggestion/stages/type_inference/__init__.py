"""Type inference stage package."""

from suggestion.stages.type_inference.contracts import SUPPORTED_INFERRED_TYPES
from suggestion.stages.type_inference.stage import TypeInferenceStage

__all__ = ["SUPPORTED_INFERRED_TYPES", "TypeInferenceStage"]
