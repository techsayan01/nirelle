"""Hand-built demo curriculum: Grade 4 Math, Fractions chapter.

Per the BRD's MVP scope ("hand-built knowledge components for one grade
and one subject/chapter only"), this is real, reviewable content for the
fractions basics typically taught right before the mid-unit test window
the product targets - not placeholder text. It covers three sub-skills
with common, well-documented misconceptions at each step:

    1. identifying numerator/denominator
    2. adding fractions with like denominators
    3. adding fractions with unlike denominators

Each sub-skill's diagnostic questions and explanation strategy are seeded
together so `nirelle.diagnostics.identify_misconception` has real,
consistent data to run against - see tests/test_end_to_end.py.

Diagnostic questions are never persisted to the DB (they're static content
shipped in code, same as the rest of this module); `nirelle.api` serves
them straight from `demo_questions()` via the `/demo/...` routes.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .db import CurriculumRepository, models
from .diagnostics import Choice, DiagnosticQuestion


@dataclass(frozen=True)
class StrategySeed:
    misconception_tag: str
    content: str
    rank: int = 0


@dataclass(frozen=True)
class SubSkillSeed:
    id: str
    name: str
    grade: int
    subject: str
    chapter: str
    strategies: tuple[StrategySeed, ...]
    diagnostic_questions: tuple[DiagnosticQuestion, ...]


_IDENTIFY_PARTS = SubSkillSeed(
    id="fractions.identify_parts",
    name="Identifying the numerator and denominator",
    grade=4,
    subject="math",
    chapter="fractions",
    strategies=(
        StrategySeed(
            misconception_tag="num_denom_swap",
            content=(
                "The denominator (bottom number) tells you how many equal parts the whole "
                "is cut into. The numerator (top number) tells you how many of those parts "
                "you have. Picture a pizza cut into 4 slices - that's a denominator of 4. "
                "If you're holding 3 of those slices, that's a numerator of 3, so 3/4 of "
                "the pizza."
            ),
        ),
    ),
    diagnostic_questions=(
        DiagnosticQuestion(
            id="ip.q1",
            sub_skill_id="fractions.identify_parts",
            difficulty=0.3,
            correct_choice_id="3_4",
            prompt="A pizza is cut into 4 equal slices. You eat 3 of them. What fraction did you eat?",
            choices=(
                Choice(id="3_4", label="3/4"),
                Choice(id="4_3", label="4/3", misconception_tag="num_denom_swap"),
                Choice(id="3_1", label="3/1"),
            ),
        ),
        DiagnosticQuestion(
            id="ip.q2",
            sub_skill_id="fractions.identify_parts",
            difficulty=0.4,
            correct_choice_id="2_5",
            prompt="A chocolate bar has 5 equal pieces. You have 2 of them. What fraction is that?",
            choices=(
                Choice(id="2_5", label="2/5"),
                Choice(id="5_2", label="5/2", misconception_tag="num_denom_swap"),
                Choice(id="2_3", label="2/3"),
            ),
        ),
    ),
)


_ADD_LIKE_DENOMINATORS = SubSkillSeed(
    id="fractions.add_like_denominators",
    name="Adding fractions with like denominators",
    grade=4,
    subject="math",
    chapter="fractions",
    strategies=(
        StrategySeed(
            misconception_tag="adds_denominators",
            content=(
                "When two fractions already have the same denominator, the whole is "
                "already cut into same-size pieces - so you only add how many pieces you "
                "have (the numerators) and keep the piece size (the denominator) the same: "
                "1/4 + 2/4 = 3/4, not 3/8."
            ),
        ),
    ),
    diagnostic_questions=(
        DiagnosticQuestion(
            id="ald.q1",
            sub_skill_id="fractions.add_like_denominators",
            difficulty=0.4,
            correct_choice_id="3_4",
            prompt="1/4 + 2/4 = ?",
            choices=(
                Choice(id="3_4", label="3/4"),
                Choice(id="3_8", label="3/8", misconception_tag="adds_denominators"),
                Choice(id="1_4", label="1/4"),
            ),
        ),
        DiagnosticQuestion(
            id="ald.q2",
            sub_skill_id="fractions.add_like_denominators",
            difficulty=0.5,
            correct_choice_id="5_6",
            prompt="2/6 + 3/6 = ?",
            choices=(
                Choice(id="5_6", label="5/6"),
                Choice(id="5_12", label="5/12", misconception_tag="adds_denominators"),
                Choice(id="2_6", label="2/6"),
            ),
        ),
    ),
)


_ADD_UNLIKE_DENOMINATORS = SubSkillSeed(
    id="fractions.add_unlike_denominators",
    name="Adding fractions with unlike denominators",
    grade=4,
    subject="math",
    chapter="fractions",
    strategies=(
        StrategySeed(
            misconception_tag="skips_common_denominator",
            content=(
                "Before adding, the pieces need to be the same size. Find a common "
                "denominator first - for 1/2 + 1/3, that's sixths (1/2 = 3/6 and "
                "1/3 = 2/6) - then add the numerators: 3/6 + 2/6 = 5/6."
            ),
        ),
        StrategySeed(
            misconception_tag="converts_only_one_fraction",
            content=(
                "Both fractions need to be rewritten with the same denominator, not just "
                "one of them - if you convert 1/2 to 3/6 for 1/2 + 1/3, you also need to "
                "convert 1/3 to 2/6 before adding, giving 3/6 + 2/6 = 5/6."
            ),
        ),
    ),
    diagnostic_questions=(
        DiagnosticQuestion(
            id="aud.q1",
            sub_skill_id="fractions.add_unlike_denominators",
            difficulty=0.7,
            correct_choice_id="5_6",
            prompt="1/2 + 1/3 = ?",
            choices=(
                Choice(id="5_6", label="5/6"),
                Choice(id="2_5", label="2/5", misconception_tag="skips_common_denominator"),
                Choice(id="4_6", label="4/6", misconception_tag="converts_only_one_fraction"),
            ),
        ),
        DiagnosticQuestion(
            id="aud.q2",
            sub_skill_id="fractions.add_unlike_denominators",
            difficulty=0.75,
            correct_choice_id="11_12",
            prompt="1/4 + 2/3 = ?",
            choices=(
                Choice(id="11_12", label="11/12"),
                Choice(id="3_7", label="3/7", misconception_tag="skips_common_denominator"),
                Choice(id="5_12", label="5/12", misconception_tag="converts_only_one_fraction"),
            ),
        ),
    ),
)


DEMO_SUB_SKILLS: tuple[SubSkillSeed, ...] = (
    _IDENTIFY_PARTS,
    _ADD_LIKE_DENOMINATORS,
    _ADD_UNLIKE_DENOMINATORS,
)


def demo_questions() -> dict[str, DiagnosticQuestion]:
    """All demo diagnostic questions, keyed by id. No DB access - this is
    static, code-shipped content, so it's available even before
    `seed_demo_curriculum` has run against a given database.
    """
    return {
        question.id: question
        for seed in DEMO_SUB_SKILLS
        for question in seed.diagnostic_questions
    }


def demo_questions_for_sub_skill(sub_skill_id: str) -> list[DiagnosticQuestion]:
    for seed in DEMO_SUB_SKILLS:
        if seed.id == sub_skill_id:
            return list(seed.diagnostic_questions)
    return []


def seed_demo_curriculum(session: Session) -> dict[str, DiagnosticQuestion]:
    """Insert the Grade 4 Math / Fractions demo curriculum into the DB.

    Idempotent - safe to call on every app startup against a persistent
    database, not just a fresh in-memory one. Returns the same
    {question_id: DiagnosticQuestion} map as `demo_questions()`.
    """
    repo = CurriculumRepository(session)

    if repo.get_sub_skill(DEMO_SUB_SKILLS[0].id) is not None:
        return demo_questions()

    for seed in DEMO_SUB_SKILLS:
        repo.add_sub_skill(
            models.SubSkill(
                id=seed.id, name=seed.name, grade=seed.grade, subject=seed.subject, chapter=seed.chapter
            )
        )
        for strategy in seed.strategies:
            repo.add_explanation_strategy(
                models.ExplanationStrategy(
                    sub_skill_id=seed.id,
                    misconception_tag=strategy.misconception_tag,
                    content=strategy.content,
                    rank=strategy.rank,
                )
            )

    return demo_questions()
