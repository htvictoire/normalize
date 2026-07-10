from __future__ import annotations

import types

import pytest

from shared.models.base import MainModel

from suggestion.ai.providers import gemini


class _Tiny(MainModel):
    value: int


class _FakeModels:
    """Returns queued reply texts and records the prompt of every call."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[str] = []

    def generate_content(self, *, model: str, contents: str, config: object) -> object:  # noqa: ARG002 — signature must match the real client
        self.calls.append(contents)
        return types.SimpleNamespace(text=self._replies.pop(0))


def _install(monkeypatch: pytest.MonkeyPatch, replies: list[str]) -> _FakeModels:
    fake_models = _FakeModels(replies)
    monkeypatch.setattr(
        gemini,
        "_genai",
        types.SimpleNamespace(
            Client=lambda api_key: types.SimpleNamespace(models=fake_models)  # noqa: ARG005
        ),
    )
    monkeypatch.setattr(
        gemini,
        "_genai_types",
        types.SimpleNamespace(
            GenerateContentConfig=lambda **kwargs: kwargs,
            ThinkingConfig=lambda **kwargs: kwargs,
        ),
    )
    monkeypatch.setattr(
        gemini,
        "get_settings",
        lambda: types.SimpleNamespace(gemini_api_key="k", gemini_model="m"),
    )
    return fake_models


def test_gemini_retries_with_corrective_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_models = _install(monkeypatch, ["this is not json", '{"value": 7}'])

    result = gemini.GeminiInferenceProvider().infer_schema("prompt", _Tiny)

    assert result == _Tiny(value=7)
    assert len(fake_models.calls) == 2
    # The retry shows the model its broken reply and asks for a correction.
    assert "this is not json" in fake_models.calls[1]
    assert "corrected JSON" in fake_models.calls[1]
    # The first attempt is not polluted with feedback.
    assert "corrected JSON" not in fake_models.calls[0]


def test_gemini_raises_after_exhausting_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_models = _install(monkeypatch, ["x", "y", "z"])

    with pytest.raises(RuntimeError, match="did not return valid _Tiny JSON"):
        gemini.GeminiInferenceProvider().infer_schema("prompt", _Tiny)

    assert len(fake_models.calls) == 3
