"""Per-file-type contracts for the AI strategy.

Inference splits at the layout. A source cannot be parsed into columns until its
SourceFormat is known, so that is the one decision everything else waits on;
column typing runs afterwards against columns that are already separated.

CSV and Excel have their layout inferred by the model. JSON declares its own —
it is self-describing, so it reaches a SourceReading without a model call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from pydantic import Field

from shared.db.column_index import build_position_to_name
from shared.models.base import MainModel
from shared.models.column import ColumnConfig, CoreColumnConfig
from shared.models.operation import SourceFormat
from shared.models.source import SourceRef
from shared.models.suggestion import LayoutConfidence

from suggestion.source import SourceReading


class LayoutAnswer(MainModel):
    """Base for a model's layout decision. Fields vary by file type."""


class ColumnTyping[ConfigT](MainModel):
    """One column's inferred type, echoed back under the name it was given."""

    name: str = Field(description="The column name exactly as supplied.")
    config: ConfigT
    confidence: float = Field(
        ge=0.0, le=1.0, description="How sure the inferred type and config are."
    )


class TypingAnswer[ConfigT](MainModel):
    """A model's typing decision for every column of one source."""

    columns: list[ColumnTyping[ConfigT]]


class ExtendedTypingAnswer(TypingAnswer[ColumnConfig]):
    """Typing across every executable column type, including the AI-only ones."""


class CoreTypingAnswer(TypingAnswer[CoreColumnConfig]):
    """Typing constrained to core non-extended column types."""


def typing_answer_for(extended_type_detection: bool) -> type[TypingAnswer[ColumnConfig]] | type[
    TypingAnswer[CoreColumnConfig]
]:
    """Return the typing output model for the selected suggestion options."""
    return ExtendedTypingAnswer if extended_type_detection else CoreTypingAnswer


def pair_typings(
    column_names: list[str],
    typings: Sequence[ColumnTyping[ColumnConfig]] | Sequence[ColumnTyping[CoreColumnConfig]],
) -> tuple[dict[str, ColumnConfig], dict[str, float]]:
    """Key a typing answer to column positions by name.

    Pairing by name rather than by order catches a model that drops, duplicates,
    or reorders a column, which positional pairing would apply to the wrong data.
    """
    position_to_name = build_position_to_name(column_names)
    by_name = {typing.name: typing for typing in typings}
    missing = [name for name in position_to_name.values() if name not in by_name]
    if missing:
        raise ValueError(f"Model returned no typing for columns: {missing}.")
    return (
        {pos: by_name[name].config for pos, name in position_to_name.items()},
        {pos: by_name[name].confidence for pos, name in position_to_name.items()},
    )


class FormatInference(ABC):
    """Reading one file type under a resolved layout."""

    @abstractmethod
    def read(self, source: SourceRef, source_format: SourceFormat) -> SourceReading:
        """Parse the source under an already-resolved layout."""


class InferredLayout[AnswerT: LayoutAnswer](FormatInference):
    """A file type whose layout the model must decide before parsing."""

    @property
    @abstractmethod
    def layout_answer(self) -> type[AnswerT]:
        """The output model the layout decision is returned in."""

    @abstractmethod
    def layout_sample(self, source: SourceRef) -> str:
        """Build the raw sample the layout decision is made from."""

    @abstractmethod
    def build_layout_prompt(self, sample: str) -> str:
        """Build the layout prompt around the sample."""

    @abstractmethod
    def to_source_format(self, answer: AnswerT, source: SourceRef) -> SourceFormat:
        """Resolve the layout the model chose into a SourceFormat."""

    @abstractmethod
    def layout_confidence(self, answer: AnswerT) -> LayoutConfidence:
        """Report how sure the model was of each layout decision it made."""


class DeclaredLayout(FormatInference):
    """A file type that describes its own layout, needing no model call."""

    @abstractmethod
    def source_format(self) -> SourceFormat:
        """Return the layout every source of this type has."""
