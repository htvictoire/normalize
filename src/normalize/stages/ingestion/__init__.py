"""
Ingestion stage package.

This package owns CSV ingestion concerns for the pipeline and exposes:
- `IngestionStage` stage adapter
- typed ingestion contracts
- strict CSV option helpers
"""

from normalize.stages.ingestion.contracts import (
    HeaderMode,
    IngestionRequest,
    IngestionResult,
)
from normalize.stages.ingestion.service import run_ingestion
from normalize.stages.ingestion.stage import IngestionStage

__all__ = [
    "HeaderMode",
    "IngestionRequest",
    "IngestionResult",
    "IngestionStage",
    "run_ingestion",
]
