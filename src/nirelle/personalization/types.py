"""Shared types for the remediation-content personalization layer.

Per the BRD: "Remediation content: drawn from a small pre-vetted library of
explanation strategies per misconception type, not freshly LLM-generated;
LLM handles only the personalization layer (wording, examples, language)
to control inference cost." `Personalizer` is that boundary - it rewrites
already-approved strategy content, it never invents new explanations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PersonalizationContext:
    """Everything a personalizer is allowed to tailor wording to. Deliberately
    narrow - name, grade, and language/tone - not free-form student data.
    """

    student_display_name: str
    grade: int
    misconception_tag: str
    language: str = "en"
    tone_hint: str | None = None


@runtime_checkable
class Personalizer(Protocol):
    """Implement this to plug in an LLM (or any other) backend. The
    contract: rewrite `strategy_content`'s wording/examples/language for
    this student; never change its underlying explanation or add new
    claims.
    """

    def personalize(self, strategy_content: str, context: PersonalizationContext) -> str: ...
