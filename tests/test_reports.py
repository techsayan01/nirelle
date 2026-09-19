from __future__ import annotations

import pytest

from nirelle.reports import build_parent_report, build_teacher_escalation


def test_build_teacher_escalation_includes_all_required_fields():
    content = build_teacher_escalation(
        student_display_name="Asha",
        sub_skill_name="Adding fractions with like denominators",
        misconception_description="adds the denominators instead of keeping them fixed",
        remediation_strategies_tried=["Number-line visual", "Fraction-bar walkthrough"],
        attempt_count=2,
        last_mastery_score=0.42,
        floor_mastery=0.75,
    )
    assert "Asha" in content.misconception_summary
    assert "adds the denominators" in content.misconception_summary
    assert "Number-line visual" in content.remediation_attempted
    assert "Fraction-bar walkthrough" in content.remediation_attempted
    assert content.attempt_count == 2
    assert "75%" in content.one_on_one_focus
    assert "42%" in content.one_on_one_focus


def test_build_teacher_escalation_handles_singular_strategy_and_attempt():
    content = build_teacher_escalation(
        student_display_name="Asha",
        sub_skill_name="Adding fractions",
        misconception_description="misc",
        remediation_strategies_tried=["One approach"],
        attempt_count=1,
        last_mastery_score=0.5,
        floor_mastery=0.75,
    )
    assert "1 remediation approach:" in content.remediation_attempted
    assert "1 re-test attempt," in content.one_on_one_focus


def test_build_teacher_escalation_rejects_empty_strategies():
    with pytest.raises(ValueError):
        build_teacher_escalation(
            student_display_name="Asha",
            sub_skill_name="Adding fractions",
            misconception_description="misc",
            remediation_strategies_tried=[],
            attempt_count=1,
            last_mastery_score=0.5,
            floor_mastery=0.75,
        )


def test_build_teacher_escalation_rejects_zero_attempt_count():
    with pytest.raises(ValueError):
        build_teacher_escalation(
            student_display_name="Asha",
            sub_skill_name="Adding fractions",
            misconception_description="misc",
            remediation_strategies_tried=["One approach"],
            attempt_count=0,
            last_mastery_score=0.5,
            floor_mastery=0.75,
        )


def test_build_parent_report_uses_plain_language_and_actions():
    content = build_parent_report(
        student_display_name="Asha",
        sub_skill_name_plain="adding fractions",
        at_home_actions=["Practice with a pizza cut into slices.", "Try 5 minutes of flashcards."],
    )
    assert "Asha" in content.plain_summary
    assert "adding fractions" in content.plain_summary
    assert "pizza" in content.at_home_actions
    assert "flashcards" in content.at_home_actions
    assert content.at_home_actions.count("\n") == 1


def test_build_parent_report_does_not_use_gendered_pronouns():
    content = build_parent_report(
        student_display_name="Asha", sub_skill_name_plain="adding fractions", at_home_actions=["Practice daily."]
    )
    lowered = content.plain_summary.lower()
    for pronoun in (" he ", " she ", " him ", " her ", " his "):
        assert pronoun not in lowered


@pytest.mark.parametrize("actions", [[], ["a", "b", "c"]])
def test_build_parent_report_rejects_wrong_number_of_actions(actions):
    with pytest.raises(ValueError):
        build_parent_report(
            student_display_name="Asha", sub_skill_name_plain="adding fractions", at_home_actions=actions
        )
