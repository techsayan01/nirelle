"""Repository layer enforcing row-level tenant isolation.

Every read/write that touches the student-state layer goes through
`TenantRepository`, which is constructed with a fixed `school_id` and folds
that filter into every query - the BRD's "row-level tenant isolation ...
every query filtered by school ID" model, enforced in one place instead of
trusted to every call site. There is no method on `TenantRepository` that
can read or write another tenant's rows.

`CurriculumRepository` is tenant-agnostic, per the BRD's curriculum layer
being global and shared across schools.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..bkt.types import AttemptEvent, LoopStage, MasteryState
from . import models


class SchoolRepository:
    """Tenant-agnostic access to school (tenant) records themselves.

    Onboarding a school is a separate step from operating within one - a
    school must exist before `TenantRepository` can write anything scoped
    to its `school_id` (enforced at the schema level via the composite
    foreign keys on `Student` and its dependents).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_school(self, school: models.School) -> models.School:
        self._session.add(school)
        self._session.flush()
        return school

    def get_school(self, school_id: str) -> models.School | None:
        return self._session.get(models.School, school_id)


class CurriculumRepository:
    """Tenant-agnostic access to the curriculum layer."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_sub_skill(self, sub_skill: models.SubSkill) -> models.SubSkill:
        self._session.add(sub_skill)
        self._session.flush()
        return sub_skill

    def get_sub_skill(self, sub_skill_id: str) -> models.SubSkill | None:
        return self._session.get(models.SubSkill, sub_skill_id)

    def list_sub_skills(
        self, grade: int | None = None, subject: str | None = None
    ) -> list[models.SubSkill]:
        stmt = select(models.SubSkill)
        if grade is not None:
            stmt = stmt.where(models.SubSkill.grade == grade)
        if subject is not None:
            stmt = stmt.where(models.SubSkill.subject == subject)
        stmt = stmt.order_by(models.SubSkill.grade, models.SubSkill.subject, models.SubSkill.name)
        return list(self._session.scalars(stmt))

    def add_explanation_strategy(
        self, strategy: models.ExplanationStrategy
    ) -> models.ExplanationStrategy:
        self._session.add(strategy)
        self._session.flush()
        return strategy

    def strategies_for_misconception(
        self, sub_skill_id: str, misconception_tag: str
    ) -> list[models.ExplanationStrategy]:
        stmt = (
            select(models.ExplanationStrategy)
            .where(
                models.ExplanationStrategy.sub_skill_id == sub_skill_id,
                models.ExplanationStrategy.misconception_tag == misconception_tag,
            )
            .order_by(models.ExplanationStrategy.rank)
        )
        return list(self._session.scalars(stmt))


class TenantRepository:
    """Student-state layer access, scoped to exactly one school."""

    def __init__(self, session: Session, school_id: str) -> None:
        self._session = session
        self.school_id = school_id

    # --- students ------------------------------------------------------

    def add_student(self, student: models.Student) -> models.Student:
        self._require_own_tenant(student.school_id)
        self._session.add(student)
        self._session.flush()
        return student

    def get_student(self, student_id: str) -> models.Student | None:
        stmt = select(models.Student).where(
            models.Student.id == student_id, models.Student.school_id == self.school_id
        )
        return self._session.scalars(stmt).one_or_none()

    # --- mastery records (mirrors nirelle.bkt.MasteryState) ------------

    def get_mastery_record(
        self, student_id: str, sub_skill_id: str
    ) -> models.MasteryRecord | None:
        stmt = select(models.MasteryRecord).where(
            models.MasteryRecord.school_id == self.school_id,
            models.MasteryRecord.student_id == student_id,
            models.MasteryRecord.sub_skill_id == sub_skill_id,
        )
        return self._session.scalars(stmt).one_or_none()

    def save_mastery_state(self, state: MasteryState, class_section: str) -> models.MasteryRecord:
        """Upsert a `nirelle.bkt.MasteryState` into this tenant's rows."""
        record = self.get_mastery_record(state.student_id, state.sub_skill_id)
        if record is None:
            record = models.MasteryRecord(
                school_id=self.school_id,
                class_section=class_section,
                student_id=state.student_id,
                sub_skill_id=state.sub_skill_id,
                p_mastery=state.p_mastery,
                stage=state.stage.value,
                cycle_count=state.cycle_count,
            )
            self._session.add(record)
        else:
            record.p_mastery = state.p_mastery
            record.stage = state.stage.value
            record.cycle_count = state.cycle_count
        self._session.flush()
        return record

    def load_mastery_state(self, student_id: str, sub_skill_id: str) -> MasteryState | None:
        """Rebuild a `nirelle.bkt.MasteryState`, including its attempt
        history, so it can be handed straight back to `MasteryEngine`.
        """
        record = self.get_mastery_record(student_id, sub_skill_id)
        if record is None:
            return None

        attempts_stmt = (
            select(models.AttemptRecord)
            .where(
                models.AttemptRecord.school_id == self.school_id,
                models.AttemptRecord.mastery_record_id == record.id,
            )
            .order_by(models.AttemptRecord.timestamp)
        )
        history = [
            AttemptEvent(
                correct=a.correct,
                response_time_ms=a.response_time_ms,
                timestamp=a.timestamp,
                stage=LoopStage(a.stage),
                misconception_tag=a.misconception_tag,
            )
            for a in self._session.scalars(attempts_stmt)
        ]

        return MasteryState(
            student_id=record.student_id,
            sub_skill_id=record.sub_skill_id,
            p_mastery=record.p_mastery,
            stage=LoopStage(record.stage),
            cycle_count=record.cycle_count,
            history=history,
        )

    def record_attempt(
        self, mastery_record: models.MasteryRecord, attempt: AttemptEvent
    ) -> models.AttemptRecord:
        self._require_own_tenant(mastery_record.school_id)
        row = models.AttemptRecord(
            school_id=self.school_id,
            class_section=mastery_record.class_section,
            mastery_record_id=mastery_record.id,
            correct=attempt.correct,
            response_time_ms=attempt.response_time_ms,
            stage=attempt.stage.value,
            misconception_tag=attempt.misconception_tag,
            timestamp=attempt.timestamp,
        )
        self._session.add(row)
        self._session.flush()
        return row

    # --- escalations / parent reports -----------------------------------

    def add_teacher_escalation(self, escalation: models.TeacherEscalation) -> models.TeacherEscalation:
        self._require_own_tenant(escalation.school_id)
        self._session.add(escalation)
        self._session.flush()
        return escalation

    def open_escalations_for_student(self, student_id: str) -> list[models.TeacherEscalation]:
        stmt = select(models.TeacherEscalation).where(
            models.TeacherEscalation.school_id == self.school_id,
            models.TeacherEscalation.student_id == student_id,
            models.TeacherEscalation.resolved_at.is_(None),
        )
        return list(self._session.scalars(stmt))

    def list_escalations(self, resolved: bool | None = None) -> list[models.TeacherEscalation]:
        """All of this school's escalations, newest first - the teacher
        dashboard's list view. `resolved=False` (open cases needing
        attention) is the common filter; `None` returns everything.
        """
        stmt = select(models.TeacherEscalation).where(
            models.TeacherEscalation.school_id == self.school_id
        )
        if resolved is True:
            stmt = stmt.where(models.TeacherEscalation.resolved_at.is_not(None))
        elif resolved is False:
            stmt = stmt.where(models.TeacherEscalation.resolved_at.is_(None))
        stmt = stmt.order_by(models.TeacherEscalation.created_at.desc())
        return list(self._session.scalars(stmt))

    def get_teacher_escalation(self, escalation_id: int) -> models.TeacherEscalation | None:
        row = self._session.get(models.TeacherEscalation, escalation_id)
        if row is None or row.school_id != self.school_id:
            return None
        return row

    def resolve_teacher_escalation_record(
        self, escalation: models.TeacherEscalation, resolved_by: str
    ) -> models.TeacherEscalation:
        self._require_own_tenant(escalation.school_id)
        escalation.resolved_at = datetime.now(timezone.utc)
        escalation.resolved_by = resolved_by
        self._session.flush()
        return escalation

    def add_parent_report(self, report: models.ParentReport) -> models.ParentReport:
        self._require_own_tenant(report.school_id)
        self._session.add(report)
        self._session.flush()
        return report

    def parent_reports_for_student(self, student_id: str) -> list[models.ParentReport]:
        stmt = (
            select(models.ParentReport)
            .where(
                models.ParentReport.school_id == self.school_id,
                models.ParentReport.student_id == student_id,
            )
            .order_by(models.ParentReport.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    # --- isolation guard --------------------------------------------------

    def _require_own_tenant(self, school_id: str) -> None:
        if school_id != self.school_id:
            raise PermissionError(
                f"TenantRepository scoped to school_id={self.school_id!r} "
                f"cannot write a row for school_id={school_id!r}"
            )
