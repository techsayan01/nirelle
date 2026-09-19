from __future__ import annotations

import pytest

from nirelle import AttemptEvent, EngineConfig, LoopStage, NotFoundError, RemediationService
from nirelle.db import CurriculumRepository, TenantRepository, create_db_engine, init_db, make_session_factory, models


@pytest.fixture
def session():
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session = make_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def school(session):
    school = models.School(id="school-a", name="Green Valley School")
    session.add(school)
    session.flush()
    return school


@pytest.fixture
def sub_skill(session):
    skill = models.SubSkill(
        id="fractions.add_like_denom",
        name="Adding fractions with like denominators",
        grade=4,
        subject="math",
        chapter="fractions",
        p_init=0.3,
        p_learn=0.15,
        p_slip=0.1,
        p_guess=0.2,
    )
    CurriculumRepository(session).add_sub_skill(skill)
    return skill


@pytest.fixture
def student(session, school):
    student = models.Student(
        school_id=school.id, id="student-1", class_section="4A", display_name="Asha"
    )
    TenantRepository(session, school_id=school.id).add_student(student)
    return student


@pytest.fixture
def service(session, school, sub_skill, student):
    return RemediationService(
        TenantRepository(session, school_id=school.id),
        CurriculumRepository(session),
        engine_config=EngineConfig(floor_mastery=0.75, max_cycles=2),
    )


def make_attempt(correct: bool) -> AttemptEvent:
    return AttemptEvent(correct=correct, response_time_ms=4000)


def test_get_or_create_state_seeds_from_sub_skill_p_init(service, sub_skill):
    state = service.get_or_create_state("student-1", sub_skill.id)
    assert state.p_mastery == sub_skill.p_init
    assert state.stage is LoopStage.DIAGNOSTIC


def test_get_or_create_state_raises_not_found_for_unknown_student(service, sub_skill):
    with pytest.raises(NotFoundError):
        service.get_or_create_state("nobody", sub_skill.id)


def test_get_or_create_state_raises_not_found_for_unknown_sub_skill(service):
    with pytest.raises(NotFoundError):
        service.get_or_create_state("student-1", "no.such.skill")


def test_record_attempt_persists_across_service_instances(session, school, sub_skill, student):
    service_1 = RemediationService(
        TenantRepository(session, school_id=school.id), CurriculumRepository(session)
    )
    service_1.record_attempt("student-1", sub_skill.id, make_attempt(True))

    # Fresh service instance (as a new request would build): must see the
    # same persisted state, proving the DB - not engine memory - is the
    # source of truth.
    service_2 = RemediationService(
        TenantRepository(session, school_id=school.id), CurriculumRepository(session)
    )
    state = service_2.get_or_create_state("student-1", sub_skill.id)
    assert state.attempt_count == 1
    assert state.p_mastery > sub_skill.p_init


def test_full_loop_reaches_escalation_and_teacher_resolution(service, sub_skill):
    student_id, skill_id = "student-1", sub_skill.id

    for _ in range(2):  # engine_config.max_cycles == 2
        service.record_attempt(student_id, skill_id, make_attempt(False))
        service.begin_remediation(student_id, skill_id)
        service.begin_retest(student_id, skill_id)
        service.record_attempt(student_id, skill_id, make_attempt(False))
        state = service.evaluate_retest(student_id, skill_id)

    assert state.stage is LoopStage.ESCALATED

    service.resolve_teacher_escalation(student_id, skill_id)
    service.record_attempt(student_id, skill_id, make_attempt(True))
    final_state = service.finalize_teacher_retest(student_id, skill_id)

    assert final_state.stage is LoopStage.RESOLVED


def test_evaluate_retest_wrong_stage_raises_value_error_not_not_found(service, sub_skill):
    service.get_or_create_state("student-1", sub_skill.id)
    with pytest.raises(ValueError):
        service.evaluate_retest("student-1", sub_skill.id)
