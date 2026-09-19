from __future__ import annotations

import pytest

from nirelle.diagnostics import (
    Choice,
    DiagnosticQuestion,
    DiagnosticResponse,
    MisconceptionConfidence,
    identify_misconception,
)


@pytest.fixture
def questions() -> dict[str, DiagnosticQuestion]:
    q1 = DiagnosticQuestion(
        id="q1",
        sub_skill_id="fractions.add_like_denom",
        difficulty=0.5,
        correct_choice_id="correct",
        choices=(
            Choice(id="correct"),
            Choice(id="adds_denominators", misconception_tag="denominator_confusion"),
            Choice(id="random_slip", misconception_tag=None),
        ),
    )
    q2 = DiagnosticQuestion(
        id="q2",
        sub_skill_id="fractions.add_like_denom",
        difficulty=0.6,
        correct_choice_id="correct",
        choices=(
            Choice(id="correct"),
            Choice(id="adds_denominators_again", misconception_tag="denominator_confusion"),
            Choice(id="wrong_numerator", misconception_tag="numerator_slip"),
        ),
    )
    q3 = DiagnosticQuestion(
        id="q3",
        sub_skill_id="fractions.add_like_denom",
        difficulty=0.7,
        correct_choice_id="correct",
        choices=(
            Choice(id="correct"),
            Choice(id="wrong_numerator_2", misconception_tag="numerator_slip"),
        ),
    )
    return {q.id: q for q in (q1, q2, q3)}


def test_identifies_the_dominant_misconception(questions):
    responses = [
        DiagnosticResponse("q1", "adds_denominators", 4000),
        DiagnosticResponse("q2", "adds_denominators_again", 4200),
        DiagnosticResponse("q3", "wrong_numerator_2", 3800),
    ]
    result = identify_misconception(questions, responses)
    assert result.confidence is MisconceptionConfidence.CONFIDENT
    assert result.tag == "denominator_confusion"
    assert result.tag_counts == {"denominator_confusion": 2, "numerator_slip": 1}
    assert result.matched_question_ids == ("q1", "q2")


def test_ambiguous_when_tags_are_tied(questions):
    responses = [
        DiagnosticResponse("q1", "adds_denominators", 4000),
        DiagnosticResponse("q3", "wrong_numerator_2", 3800),
    ]
    result = identify_misconception(questions, responses)
    assert result.confidence is MisconceptionConfidence.AMBIGUOUS
    assert result.tag is None
    assert result.tag_counts == {"denominator_confusion": 1, "numerator_slip": 1}


def test_none_when_all_correct(questions):
    responses = [DiagnosticResponse("q1", "correct", 3000)]
    result = identify_misconception(questions, responses)
    assert result.confidence is MisconceptionConfidence.NONE
    assert result.tag is None


def test_none_when_wrong_answers_are_untagged(questions):
    responses = [DiagnosticResponse("q1", "random_slip", 3000)]
    result = identify_misconception(questions, responses)
    assert result.confidence is MisconceptionConfidence.NONE


def test_none_with_no_responses(questions):
    result = identify_misconception(questions, [])
    assert result.confidence is MisconceptionConfidence.NONE


def test_question_rejects_correct_choice_not_in_choices():
    with pytest.raises(ValueError):
        DiagnosticQuestion(
            id="bad",
            sub_skill_id="s",
            difficulty=0.5,
            correct_choice_id="missing",
            choices=(Choice(id="a"), Choice(id="b")),
        )


def test_question_rejects_duplicate_choice_ids():
    with pytest.raises(ValueError):
        DiagnosticQuestion(
            id="bad",
            sub_skill_id="s",
            difficulty=0.5,
            correct_choice_id="a",
            choices=(Choice(id="a"), Choice(id="a")),
        )


def test_question_rejects_out_of_range_difficulty():
    with pytest.raises(ValueError):
        DiagnosticQuestion(
            id="bad",
            sub_skill_id="s",
            difficulty=1.5,
            correct_choice_id="a",
            choices=(Choice(id="a"),),
        )
