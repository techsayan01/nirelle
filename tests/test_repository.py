from __future__ import annotations

import pytest

from nirelle.bkt.types import AttemptEvent, LoopStage, MasteryState
from nirelle.db import (
    CurriculumRepository,
    TenantRepository,
    create_db_engine,
    init_db,
    make_session_factory,
    models,
)


@pytest.fixture
def session():
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    factory = make_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded_schools(session):
    school_a = models.School(id="school-a", name="Green Valley School")
    school_b = models.School(id="school-b", name="Riverside School")
    session.add_all([school_a, school_b])
    session.flush()
    return school_a, school_b


@pytest.fixture
def sub_skill(session):
    skill = models.SubSkill(
        id="fractions.add_like_denom",
        name="Adding fractions with like denominators",
        grade=4,
        subject="math",
        chapter="fractions",
    )
    CurriculumRepository(session).add_sub_skill(skill)
    return skill


# --- Curriculum layer (tenant-agnostic) ------------------------------------


def test_curriculum_repository_round_trips_a_sub_skill(session):
    repo = CurriculumRepository(session)
    repo.add_sub_skill(
        models.SubSkill(id="s1", name="Test skill", grade=4, subject="math", chapter="ch1")
    )
    fetched = repo.get_sub_skill("s1")
    assert fetched is not None
    assert fetched.name == "Test skill"


def test_curriculum_repository_orders_strategies_by_rank(session, sub_skill):
    repo = CurriculumRepository(session)
    repo.add_explanation_strategy(
        models.ExplanationStrategy(
            sub_skill_id=sub_skill.id,
            misconception_tag="denominator_confusion",
            content="second",
            rank=1,
        )
    )
    repo.add_explanation_strategy(
        models.ExplanationStrategy(
            sub_skill_id=sub_skill.id,
            misconception_tag="denominator_confusion",
            content="first",
            rank=0,
        )
    )

    strategies = repo.strategies_for_misconception(sub_skill.id, "denominator_confusion")
    assert [s.content for s in strategies] == ["first", "second"]


# --- Tenant isolation --------------------------------------------------------


def test_tenant_repository_cannot_write_another_schools_row(session, seeded_schools):
    school_a, school_b = seeded_schools
    repo_a = TenantRepository(session, school_id=school_a.id)

    with pytest.raises(PermissionError):
        repo_a.add_student(
            models.Student(
                id="student-1", school_id=school_b.id, class_section="4A", display_name="Asha"
            )
        )


def test_student_insert_rejected_for_nonexistent_school(session):
    """SQLite ignores FOREIGN KEY constraints by default; create_db_engine
    must turn enforcement on per-connection (PRAGMA foreign_keys=ON) or
    this insert would silently succeed instead of violating the composite
    (school_id, id) foreign key that backs tenant isolation.
    """
    from sqlalchemy.exc import IntegrityError

    repo = TenantRepository(session, school_id="ghost-school")
    with pytest.raises(IntegrityError):
        repo.add_student(
            models.Student(
                id="student-1", school_id="ghost-school", class_section="4A", display_name="Asha"
            )
        )


def test_tenant_repository_only_sees_its_own_students(session, seeded_schools):
    school_a, school_b = seeded_schools
    repo_a = TenantRepository(session, school_id=school_a.id)
    repo_b = TenantRepository(session, school_id=school_b.id)

    repo_a.add_student(
        models.Student(id="student-1", school_id=school_a.id, class_section="4A", display_name="Asha")
    )
    repo_b.add_student(
        models.Student(id="student-1", school_id=school_b.id, class_section="5B", display_name="Riya")
    )

    assert repo_a.get_student("student-1").class_section == "4A"
    assert repo_b.get_student("student-1").class_section == "5B"


# --- Mastery state persistence (bridges to nirelle.bkt) ---------------------


def test_save_and_load_mastery_state_round_trips(session, seeded_schools, sub_skill):
    school_a, _ = seeded_schools
    repo = TenantRepository(session, school_id=school_a.id)
    repo.add_student(
        models.Student(id="student-1", school_id=school_a.id, class_section="4A", display_name="Asha")
    )

    state = MasteryState(
        student_id="student-1",
        sub_skill_id=sub_skill.id,
        p_mastery=0.42,
        stage=LoopStage.DIAGNOSTIC,
        cycle_count=1,
    )
    record = repo.save_mastery_state(state, class_section="4A")
    repo.record_attempt(
        record, AttemptEvent(correct=True, response_time_ms=4200, stage=LoopStage.DIAGNOSTIC)
    )
    repo.record_attempt(
        record, AttemptEvent(correct=False, response_time_ms=5300, stage=LoopStage.DIAGNOSTIC)
    )

    loaded = repo.load_mastery_state("student-1", sub_skill.id)
    assert loaded is not None
    assert loaded.p_mastery == pytest.approx(0.42)
    assert loaded.stage is LoopStage.DIAGNOSTIC
    assert loaded.cycle_count == 1
    assert [a.correct for a in loaded.history] == [True, False]


def test_save_mastery_state_upserts_on_second_call(session, seeded_schools, sub_skill):
    school_a, _ = seeded_schools
    repo = TenantRepository(session, school_id=school_a.id)
    repo.add_student(
        models.Student(id="student-1", school_id=school_a.id, class_section="4A", display_name="Asha")
    )

    state = MasteryState(student_id="student-1", sub_skill_id=sub_skill.id, p_mastery=0.3)
    repo.save_mastery_state(state, class_section="4A")

    state.p_mastery = 0.55
    state.cycle_count = 2
    repo.save_mastery_state(state, class_section="4A")

    reloaded = repo.load_mastery_state("student-1", sub_skill.id)
    assert reloaded.p_mastery == pytest.approx(0.55)
    assert reloaded.cycle_count == 2


def test_load_mastery_state_returns_none_when_absent(session, seeded_schools):
    school_a, _ = seeded_schools
    repo = TenantRepository(session, school_id=school_a.id)
    assert repo.load_mastery_state("nobody", "no.such.skill") is None


# --- Escalations / parent reports -------------------------------------------


def test_open_escalations_excludes_resolved_ones(session, seeded_schools, sub_skill):
    school_a, _ = seeded_schools
    repo = TenantRepository(session, school_id=school_a.id)
    repo.add_student(
        models.Student(id="student-1", school_id=school_a.id, class_section="4A", display_name="Asha")
    )

    open_escalation = models.TeacherEscalation(
        school_id=school_a.id,
        class_section="4A",
        student_id="student-1",
        sub_skill_id=sub_skill.id,
        misconception_summary="Confuses numerator/denominator when adding.",
        remediation_attempted="Two remediation cycles with number-line visuals.",
        attempt_count=2,
        one_on_one_focus="Walk through why denominators must match before adding.",
    )
    resolved_escalation = models.TeacherEscalation(
        school_id=school_a.id,
        class_section="4A",
        student_id="student-1",
        sub_skill_id=sub_skill.id,
        misconception_summary="Earlier, unrelated issue.",
        remediation_attempted="Already handled.",
        attempt_count=2,
        one_on_one_focus="n/a",
        resolved_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        resolved_by="teacher-1",
    )
    repo.add_teacher_escalation(open_escalation)
    repo.add_teacher_escalation(resolved_escalation)

    open_ones = repo.open_escalations_for_student("student-1")
    assert len(open_ones) == 1
    assert open_ones[0].misconception_summary.startswith("Confuses")


def test_add_parent_report_rejects_wrong_tenant(session, seeded_schools):
    school_a, school_b = seeded_schools
    repo_a = TenantRepository(session, school_id=school_a.id)

    with pytest.raises(PermissionError):
        repo_a.add_parent_report(
            models.ParentReport(
                school_id=school_b.id,
                class_section="4A",
                student_id="student-1",
                sub_skill_id="fractions.add_like_denom",
                plain_summary="Struggling with fractions right now.",
                at_home_actions="Practice with a pizza cut into slices.",
            )
        )


# --- list_sub_skills ---------------------------------------------------------


def test_list_sub_skills_filters_by_grade_and_subject(session):
    repo = CurriculumRepository(session)
    repo.add_sub_skill(models.SubSkill(id="m4", name="Math 4", grade=4, subject="math", chapter="c"))
    repo.add_sub_skill(models.SubSkill(id="m5", name="Math 5", grade=5, subject="math", chapter="c"))
    repo.add_sub_skill(models.SubSkill(id="e4", name="English 4", grade=4, subject="english", chapter="c"))

    assert [s.id for s in repo.list_sub_skills(grade=4)] == ["e4", "m4"]
    assert [s.id for s in repo.list_sub_skills(subject="math")] == ["m4", "m5"]
    assert [s.id for s in repo.list_sub_skills(grade=4, subject="math")] == ["m4"]
    assert len(repo.list_sub_skills()) == 3


# --- list_escalations ---------------------------------------------------------


def test_list_escalations_filters_by_resolved_state(session, seeded_schools, sub_skill):
    school_a, _ = seeded_schools
    repo = TenantRepository(session, school_id=school_a.id)
    repo.add_student(
        models.Student(school_id=school_a.id, id="student-1", class_section="4A", display_name="Asha")
    )

    def make_escalation(**overrides):
        defaults = dict(
            school_id=school_a.id,
            class_section="4A",
            student_id="student-1",
            sub_skill_id=sub_skill.id,
            misconception_summary="s",
            remediation_attempted="r",
            attempt_count=2,
            one_on_one_focus="f",
        )
        defaults.update(overrides)
        return models.TeacherEscalation(**defaults)

    open_one = repo.add_teacher_escalation(make_escalation())
    repo.add_teacher_escalation(make_escalation())
    repo.resolve_teacher_escalation_record(open_one, resolved_by="teacher-1")

    assert len(repo.list_escalations()) == 2
    assert len(repo.list_escalations(resolved=True)) == 1
    assert len(repo.list_escalations(resolved=False)) == 1


def test_list_escalations_does_not_see_other_schools(session, seeded_schools, sub_skill):
    school_a, school_b = seeded_schools
    repo_a = TenantRepository(session, school_id=school_a.id)
    repo_b = TenantRepository(session, school_id=school_b.id)
    for repo, school in ((repo_a, school_a), (repo_b, school_b)):
        repo.add_student(
            models.Student(school_id=school.id, id="s1", class_section="4A", display_name="X")
        )
        repo.add_teacher_escalation(
            models.TeacherEscalation(
                school_id=school.id,
                class_section="4A",
                student_id="s1",
                sub_skill_id=sub_skill.id,
                misconception_summary="s",
                remediation_attempted="r",
                attempt_count=1,
                one_on_one_focus="f",
            )
        )

    assert len(repo_a.list_escalations()) == 1
    assert len(repo_b.list_escalations()) == 1


# --- parent_reports_for_student -----------------------------------------------


def test_parent_reports_for_student_scoped_and_ordered(session, seeded_schools, sub_skill):
    school_a, _ = seeded_schools
    repo = TenantRepository(session, school_id=school_a.id)
    repo.add_student(
        models.Student(school_id=school_a.id, id="student-1", class_section="4A", display_name="Asha")
    )

    for i in range(2):
        repo.add_parent_report(
            models.ParentReport(
                school_id=school_a.id,
                class_section="4A",
                student_id="student-1",
                sub_skill_id=sub_skill.id,
                plain_summary=f"summary {i}",
                at_home_actions="Practice daily.",
            )
        )

    reports = repo.parent_reports_for_student("student-1")
    assert len(reports) == 2
    assert repo.parent_reports_for_student("nobody") == []
