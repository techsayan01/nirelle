from __future__ import annotations

import sys
import types
from dataclasses import dataclass

import pytest

from nirelle.personalization import (
    AnthropicPersonalizer,
    IdentityPersonalizer,
    PersonalizationContext,
    TemplatePersonalizer,
)


def make_context(**overrides) -> PersonalizationContext:
    defaults = dict(
        student_display_name="Asha",
        grade=4,
        misconception_tag="denominator_confusion",
    )
    defaults.update(overrides)
    return PersonalizationContext(**defaults)


def test_identity_personalizer_returns_content_unchanged():
    personalizer = IdentityPersonalizer()
    content = "Add the numerators when denominators match."
    assert personalizer.personalize(content, make_context()) == content


def test_template_personalizer_prepends_named_opener():
    personalizer = TemplatePersonalizer()
    result = personalizer.personalize(
        "Core explanation.", make_context(student_display_name="Riya")
    )
    assert "Riya" in result
    assert "Core explanation." in result


def test_template_personalizer_uses_tone_hint():
    personalizer = TemplatePersonalizer()
    result = personalizer.personalize(
        "Core explanation.", make_context(student_display_name="Riya", tone_hint="concise")
    )
    assert result.startswith("Riya, here's the key idea.")


def test_template_personalizer_falls_back_to_default_opener_for_unknown_tone():
    personalizer = TemplatePersonalizer()
    result = personalizer.personalize(
        "Core explanation.", make_context(student_display_name="Riya", tone_hint="sarcastic")
    )
    assert result.startswith("Hi Riya,")


# --- AnthropicPersonalizer: exercised against a fake `anthropic` module,
# never a real network call. ------------------------------------------------


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


class _FakeMessages:
    def __init__(self, calls: list[dict]) -> None:
        self._calls = calls

    def create(self, **kwargs):
        self._calls.append(kwargs)
        return types.SimpleNamespace(content=[_FakeTextBlock(text="Rewritten for Asha!")])


class _FakeAnthropicClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.calls: list[dict] = []
        self.messages = _FakeMessages(self.calls)


@pytest.fixture
def fake_anthropic_module(monkeypatch):
    holder: dict[str, _FakeAnthropicClient] = {}

    def _Anthropic(api_key: str) -> _FakeAnthropicClient:
        client = _FakeAnthropicClient(api_key)
        holder["client"] = client
        return client

    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = _Anthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return holder


def test_anthropic_personalizer_calls_api_and_returns_rewritten_text(fake_anthropic_module):
    personalizer = AnthropicPersonalizer(api_key="fake-key")
    result = personalizer.personalize(
        "Add the numerators when denominators match.", make_context()
    )
    assert result == "Rewritten for Asha!"

    client = fake_anthropic_module["client"]
    assert client.api_key == "fake-key"
    assert len(client.calls) == 1
    sent_prompt = client.calls[0]["messages"][0]["content"]
    assert "Asha" in sent_prompt
    assert "denominator_confusion" in sent_prompt


def test_anthropic_personalizer_rejects_empty_api_key(fake_anthropic_module):
    with pytest.raises(ValueError):
        AnthropicPersonalizer(api_key="")


def test_anthropic_personalizer_raises_helpful_error_without_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)  # forces ImportError on import
    with pytest.raises(ImportError, match=r"pip install nirelle\[llm\]"):
        AnthropicPersonalizer(api_key="fake-key")
