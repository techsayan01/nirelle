"""Integration test walking the full BRD flowchart against the demo
curriculum: diagnostic responses -> misconception identified ->
personalized remediation -> re-test -> resolved. Each piece has its own
focused unit tests elsewhere; this proves they compose.
"""
from __future__ import annotations

import pytest

from nirelle import AttemptEvent, EngineConfig, LoopStage, RemediationService
from nirelle.db import CurriculumRepository, TenantRepository, create_db_engine, init_db, make_session_factory, models
from nirelle.diagnostics import DiagnosticResponse, MisconceptionConfidence, identify_misconception
from nirelle.personalization import PersonalizationContext, TemplatePersonalizer
from nirelle.seed_data import seed_demo_curriculum


@pytest.fixture
def session():
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session = make_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()


def test_full_remediation_loop_against_demo_curriculum(session):
    questions = seed_demo_curriculum(session)
    sub_skill_id = "fractions.add_like_denominators"

    school = models.School(id="demo-school", name="Demo Pilot School")
    session.add(school)
    session.flush()

    tenant_repo = TenantRepository(session, school_id=school.id)
    tenant_repo.add_student(
        models.Student(school_id=school.id, id="s1", class_section="4A", display_name="Asha")
    )

    service = RemediationService(
        tenant_repo, CurriculumRepository(session), engine_config=EngineConfig(floor_mastery=0.75)
    )

    # 1. Diagnostic: Asha answers both like-denominator questions with the
    # "adds the denominators too" distractor.
    diagnostic_responses = [
        DiagnosticResponse(question_id="ald.q1", selected_choice_id="3_8", response_time_ms=5200),
        DiagnosticResponse(question_id="ald.q2", selected_choice_id="5_12", response_time_ms=4900),
    ]
    misconception = identify_misconception(questions, diagnostic_responses)
    assert misconception.confidence is MisconceptionConfidence.CONFIDENT
    assert misconception.tag == "adds_denominators"

    for response in diagnostic_responses:
        question = questions[response.question_id]
        service.record_attempt(
            "s1",
            sub_skill_id,
            AttemptEvent(
                correct=(response.selected_choice_id == question.correct_choice_id),
                response_time_ms=response.response_time_ms,
                stage=LoopStage.DIAGNOSTIC,
                misconception_tag=misconception.tag,
            ),
        )

    state = service.get_or_create_state("s1", sub_skill_id)
    assert state.attempt_count == 2
    assert not service.is_above_floor(state)

    # 2. Remediation: pull the pre-vetted strategy for that misconception
    # and personalize its wording for Asha - the content itself must stay
    # unchanged, only the wording wraps it.
    strategies = CurriculumRepository(session).strategies_for_misconception(
        sub_skill_id, misconception.tag
    )
    assert len(strategies) == 1
    personalized = TemplatePersonalizer().personalize(
        strategies[0].content,
        PersonalizationContext(
            student_display_name="Asha", grade=4, misconception_tag=misconception.tag
        ),
    )
    assert "Asha" in personalized
    assert "add how many pieces you have" in personalized  # original explanation preserved

    service.begin_remediation("s1", sub_skill_id)

    # 3. Re-test: Asha now answers correctly.
    service.begin_retest("s1", sub_skill_id)
    for _ in range(2):
        service.record_attempt(
            "s1", sub_skill_id, AttemptEvent(correct=True, response_time_ms=4000, stage=LoopStage.RETEST)
        )

    final_state = service.evaluate_retest("s1", sub_skill_id)
    assert final_state.stage is LoopStage.RESOLVED
    assert service.is_above_floor(final_state)
