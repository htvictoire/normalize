"""Suggestion pipeline dispatcher — routes each phase to its selected strategy.

Layout and typing are independently selectable, so the common case (both phases
on the same strategy) and the mixed case (one phase per strategy) are both
supported. The same-strategy case is dispatched to that strategy's own combined
``run_suggestion``, which reads the source once for both phases; the mixed case
composes the two phases separately, each reading the source under the format the
layout phase resolved.
"""

from __future__ import annotations

from shared.models.suggestion import LayoutOutput, SuggestionInput, TypingOutput

from suggestion.ai import run_layout as ai_run_layout
from suggestion.ai import run_suggestion as ai_run_suggestion
from suggestion.ai import run_typing as ai_run_typing
from suggestion.rule_based.pipeline import run_layout as rule_based_run_layout
from suggestion.rule_based.pipeline import run_suggestion as rule_based_run_suggestion
from suggestion.rule_based.pipeline import run_typing as rule_based_run_typing


def run_layout(request: SuggestionInput) -> LayoutOutput:
    """Resolve one source's layout using the selected layout strategy."""
    if request.layout_method == "ai":
        return ai_run_layout(request)
    return rule_based_run_layout(request)


def run_typing(request: SuggestionInput, layout: LayoutOutput) -> TypingOutput:
    """Type the columns of an already-resolved layout using the selected typing strategy."""
    if request.typing_method == "ai":
        return ai_run_typing(request, layout)
    return rule_based_run_typing(request, layout)


def run_suggestion(request: SuggestionInput) -> tuple[LayoutOutput, TypingOutput]:
    """Run both suggestion phases for one source file."""
    if request.layout_method == request.typing_method == "rule_based":
        return rule_based_run_suggestion(request)
    if request.layout_method == request.typing_method == "ai":
        return ai_run_suggestion(request)
    layout = run_layout(request)
    return layout, run_typing(request, layout)
