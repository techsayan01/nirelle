"""Teacher-escalation and parent-report content generation.

Both are template-driven, not LLM-driven: per the BRD, the LLM's job is
personalizing remediation wording for the student (see
`nirelle.personalization`), not writing the teacher/parent-facing reports.
"Personalized" in the BRD's teacher-escalation requirement reads as
*specific to this student's actual diagnostic history* (not a raw data
dump), which these templates satisfy by construction - every field is
built from that student's real mastery/misconception/attempt data, not
generic boilerplate.

Output field names match `nirelle.db.models.TeacherEscalation` /
`ParentReport` exactly, so a result here can be spread straight into the
ORM row: `models.TeacherEscalation(school_id=..., **asdict(content))`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TeacherEscalationContent:
    misconception_summary: str
    remediation_attempted: str
    attempt_count: int
    one_on_one_focus: str


@dataclass(frozen=True)
class ParentReportContent:
    plain_summary: str
    at_home_actions: str  # newline-separated, 1-2 items per the BRD


def build_teacher_escalation(
    student_display_name: str,
    sub_skill_name: str,
    misconception_description: str,
    remediation_strategies_tried: list[str],
    attempt_count: int,
    last_mastery_score: float,
    floor_mastery: float,
) -> TeacherEscalationContent:
    """Build the teacher-facing summary from this specific student's
    diagnostic history, per the BRD: "not a raw data dump" - must show the
    misconception, what's been tried, and a precise summary of what to
    target in the 1-on-1.
    """
    if not remediation_strategies_tried:
        raise ValueError("remediation_strategies_tried must not be empty")
    if attempt_count < 1:
        raise ValueError(f"attempt_count={attempt_count!r} must be >= 1")

    strategies_joined = ", ".join(remediation_strategies_tried)
    strategy_plural = "es" if len(remediation_strategies_tried) != 1 else ""
    remediation_attempted = (
        f"Tried {len(remediation_strategies_tried)} remediation approach{strategy_plural}: "
        f"{strategies_joined}."
    )

    misconception_summary = (
        f"{student_display_name} shows a persistent misconception in {sub_skill_name}: "
        f"{misconception_description}"
    )

    attempt_plural = "s" if attempt_count != 1 else ""
    one_on_one_focus = (
        f"Focus the 1-on-1 on: {misconception_description} "
        f"After {attempt_count} re-test attempt{attempt_plural}, {student_display_name} is "
        f"still below the {floor_mastery:.0%} mastery floor (last score: {last_mastery_score:.0%})."
    )

    return TeacherEscalationContent(
        misconception_summary=misconception_summary,
        remediation_attempted=remediation_attempted,
        attempt_count=attempt_count,
        one_on_one_focus=one_on_one_focus,
    )


def build_parent_report(
    student_display_name: str,
    sub_skill_name_plain: str,
    at_home_actions: list[str],
) -> ParentReportContent:
    """Build the parent-facing report: high-level, plain language, no
    misconception-level jargon, 1-2 concrete at-home actions per the BRD.
    """
    if not 1 <= len(at_home_actions) <= 2:
        raise ValueError(
            f"at_home_actions must have 1-2 items per the BRD, got {len(at_home_actions)}"
        )

    plain_summary = (
        f"{student_display_name} is having some trouble with {sub_skill_name_plain} right now. "
        "We've tried a couple of different explanations at school, and a little extra "
        "practice at home would help too."
    )

    return ParentReportContent(
        plain_summary=plain_summary,
        at_home_actions="\n".join(at_home_actions),
    )
