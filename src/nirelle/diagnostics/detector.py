"""Misconception detection: turns a diagnostic session's wrong answers into
the "Misconception identified" step of the BRD's remediation-loop
flowchart.

This works by lookup, not inference: each diagnostic question's distractor
choices are pre-tagged (by curriculum design, not an LLM) with the specific
misconception they reveal. Detection just tallies which tag comes up most
often across the session's wrong answers.
"""
from __future__ import annotations

from .types import (
    DiagnosticQuestion,
    DiagnosticResponse,
    MisconceptionConfidence,
    MisconceptionResult,
)


def identify_misconception(
    questions: dict[str, DiagnosticQuestion],
    responses: list[DiagnosticResponse],
) -> MisconceptionResult:
    """Tally misconception tags across a diagnostic session's wrong answers.

    Returns CONFIDENT with the single most-tagged misconception when one
    tag clearly leads; AMBIGUOUS when two or more tags are tied for the
    lead (the diagnostic didn't yet isolate a single misconception - ask
    another question); NONE when there were no wrong, tagged answers to
    go on.
    """
    tag_counts: dict[str, int] = {}
    tag_question_ids: dict[str, list[str]] = {}

    for response in responses:
        question = questions[response.question_id]
        if response.selected_choice_id == question.correct_choice_id:
            continue

        choice = question.choice(response.selected_choice_id)
        if choice.misconception_tag is None:
            continue

        tag_counts[choice.misconception_tag] = tag_counts.get(choice.misconception_tag, 0) + 1
        tag_question_ids.setdefault(choice.misconception_tag, []).append(question.id)

    if not tag_counts:
        return MisconceptionResult(
            tag=None, confidence=MisconceptionConfidence.NONE, tag_counts={}, matched_question_ids=()
        )

    max_count = max(tag_counts.values())
    leading_tags = [tag for tag, count in tag_counts.items() if count == max_count]

    if len(leading_tags) > 1:
        return MisconceptionResult(
            tag=None,
            confidence=MisconceptionConfidence.AMBIGUOUS,
            tag_counts=tag_counts,
            matched_question_ids=(),
        )

    leading_tag = leading_tags[0]
    return MisconceptionResult(
        tag=leading_tag,
        confidence=MisconceptionConfidence.CONFIDENT,
        tag_counts=tag_counts,
        matched_question_ids=tuple(tag_question_ids[leading_tag]),
    )
