"""Shared data types for misconception detection from diagnostic responses."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Choice:
    """One answer option for a diagnostic question.

    ``misconception_tag`` is None for the correct choice, or for a
    distractor that isn't mapped to any specific known misconception
    (e.g. a plain arithmetic slip rather than a conceptual error).

    ``label`` is the display text shown to the student (e.g. "3/4"). It
    defaults to empty for callers that only need the detection logic
    (existing tests, programmatic question banks); UI-facing content like
    `nirelle.seed_data` sets it.
    """

    id: str
    misconception_tag: str | None = None
    label: str = ""


@dataclass(frozen=True)
class DiagnosticQuestion:
    """A multiple-choice diagnostic question whose wrong-answer choices are
    pre-tagged with the misconception they reveal - this is what makes
    misconception detection a lookup instead of free-text interpretation.
    """

    id: str
    sub_skill_id: str
    difficulty: float
    correct_choice_id: str
    choices: tuple[Choice, ...]
    prompt: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.difficulty <= 1.0:
            raise ValueError(f"difficulty={self.difficulty!r} must be in [0, 1]")
        choice_ids = {c.id for c in self.choices}
        if len(choice_ids) != len(self.choices):
            raise ValueError(f"duplicate choice ids in question {self.id!r}")
        if self.correct_choice_id not in choice_ids:
            raise ValueError(
                f"correct_choice_id={self.correct_choice_id!r} is not among the choices "
                f"of question {self.id!r}"
            )

    def choice(self, choice_id: str) -> Choice:
        for c in self.choices:
            if c.id == choice_id:
                return c
        raise KeyError(f"choice_id={choice_id!r} not found on question {self.id!r}")


@dataclass(frozen=True)
class DiagnosticResponse:
    """A student's answer to one diagnostic question."""

    question_id: str
    selected_choice_id: str
    response_time_ms: int


class MisconceptionConfidence(str, Enum):
    NONE = "none"  # no wrong answers, or none of them were tagged
    AMBIGUOUS = "ambiguous"  # two or more misconceptions tied for most common
    CONFIDENT = "confident"


@dataclass(frozen=True)
class MisconceptionResult:
    """The outcome of running `identify_misconception` over one diagnostic
    session.
    """

    tag: str | None
    confidence: MisconceptionConfidence
    tag_counts: dict[str, int]
    matched_question_ids: tuple[str, ...]
