"""Concrete `Personalizer` implementations.

`IdentityPersonalizer` and `TemplatePersonalizer` are deterministic and
dependency-free - useful as the default, in tests, and as a safe fallback
if an LLM call fails. `AnthropicPersonalizer` is the real LLM-backed
option; it lazily imports the `anthropic` package so the rest of this
package doesn't need it installed to run.
"""
from __future__ import annotations

from .types import PersonalizationContext


class IdentityPersonalizer:
    """Returns the pre-vetted strategy content unchanged. The safe default:
    zero inference cost, zero risk of drifting from the vetted explanation.
    """

    def personalize(self, strategy_content: str, context: PersonalizationContext) -> str:
        return strategy_content


class TemplatePersonalizer:
    """Deterministic, LLM-free personalization: drops the student's name in
    and swaps in a tone-appropriate opener. Good enough for a demo, and a
    reasonable fallback when no LLM backend is configured.
    """

    _OPENERS = {
        "encouraging": "You're close, {name} - let's look at this a different way.",
        "concise": "{name}, here's the key idea.",
    }
    _DEFAULT_OPENER = "Hi {name}, let's work through this together."

    def personalize(self, strategy_content: str, context: PersonalizationContext) -> str:
        opener_template = self._OPENERS.get(context.tone_hint or "", self._DEFAULT_OPENER)
        opener = opener_template.format(name=context.student_display_name)
        return f"{opener}\n\n{strategy_content}"


class AnthropicPersonalizer:
    """Rewrites strategy content's wording/examples/language via the
    Claude API. Requires the optional `anthropic` package (`pip install
    nirelle[llm]`) and an API key; both are validated at construction so
    failures surface immediately rather than on first use.

    This only ever asks the model to rephrase pre-approved content for one
    student's context - never to invent new explanations - per the BRD's
    "LLM handles only the personalization layer" requirement.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-5",
        max_tokens: int = 512,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
            raise ImportError(
                "AnthropicPersonalizer requires the 'anthropic' package. "
                "Install it with: pip install nirelle[llm]"
            ) from exc

        if not api_key:
            raise ValueError("api_key must be a non-empty string")

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def personalize(self, strategy_content: str, context: PersonalizationContext) -> str:
        prompt = (
            "Rewrite the following math-remediation explanation for a grade "
            f"{context.grade} student named {context.student_display_name}. "
            "Keep every mathematical claim and step identical - only adjust "
            "wording, examples, and tone so it reads naturally for this "
            f"student. Misconception being addressed: {context.misconception_tag}. "
            f"Language: {context.language}."
            + (f" Tone: {context.tone_hint}." if context.tone_hint else "")
            + f"\n\nExplanation:\n{strategy_content}"
        )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
