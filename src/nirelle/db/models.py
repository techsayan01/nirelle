"""SQLAlchemy models for the two-layer schema from the BRD's "Data
architecture and multi-tenancy" section:

    Curriculum layer   - global, tenant-agnostic: sub-skills, prerequisite
                          links, the pre-vetted explanation-strategy
                          library.
    Student-state layer - per-tenant, strictly isolated: student profiles,
                          mastery per sub-skill, attempt history, teacher
                          escalations, parent reports. Every record carries
                          a school ID and class/section ID.

MVP isolation model per the BRD: row-level tenant isolation in a single
shared database, every query filtered by school ID (see
`nirelle.db.repository`), rather than physical per-school databases -
chosen for build speed within the 6-week / one-pilot-school timeline.

Student IDs are school-local (roll number / admission number, as issued by
the school's own SIS), not globally unique, so `Student` uses a composite
primary key of `(school_id, id)` and every table that references a student
carries a matching composite foreign key. This also means the DB layer
itself enforces isolation at the schema level, not just in application
code: a row can't reference a student in a different school.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# --- Curriculum layer (global, tenant-agnostic) -----------------------------


class SubSkill(Base):
    """One knowledge component: e.g. "fractions.add_like_denominator".

    Carries its own BKT parameters (see `nirelle.bkt.SkillParams`) since
    they're curriculum-layer facts about the skill, shared across every
    tenant - not something each school tunes independently.
    """

    __tablename__ = "sub_skills"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    chapter: Mapped[str] = mapped_column(String, nullable=False)

    p_init: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    p_learn: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    p_slip: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    p_guess: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)

    explanation_strategies: Mapped[list["ExplanationStrategy"]] = relationship(
        back_populates="sub_skill", cascade="all, delete-orphan"
    )


class SubSkillPrerequisite(Base):
    """Self-referential prerequisite links between sub-skills."""

    __tablename__ = "sub_skill_prerequisites"

    sub_skill_id: Mapped[str] = mapped_column(
        ForeignKey("sub_skills.id"), primary_key=True
    )
    prerequisite_id: Mapped[str] = mapped_column(
        ForeignKey("sub_skills.id"), primary_key=True
    )


class ExplanationStrategy(Base):
    """One pre-vetted explanation strategy for one misconception type.

    The LLM personalizes wording/examples/language on top of this content
    (per the BRD's remediation-content requirement); it does not generate
    the strategy itself.
    """

    __tablename__ = "explanation_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_skill_id: Mapped[str] = mapped_column(ForeignKey("sub_skills.id"), nullable=False)
    misconception_tag: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sub_skill: Mapped[SubSkill] = relationship(back_populates="explanation_strategies")


# --- Student-state layer (per-tenant, isolated by school_id) ---------------


class School(Base):
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Student(Base):
    """`id` is school-local (a roll/admission number), not globally
    unique - the primary key is the (school_id, id) pair.
    """

    __tablename__ = "students"

    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), primary_key=True)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    class_section: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)


class MasteryRecord(Base):
    """Persisted mirror of `nirelle.bkt.MasteryState` for one
    (student, sub-skill) pair.
    """

    __tablename__ = "mastery_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["school_id", "student_id"], ["students.school_id", "students.id"]
        ),
        UniqueConstraint("school_id", "student_id", "sub_skill_id", name="uq_mastery_record"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    class_section: Mapped[str] = mapped_column(String, nullable=False)
    student_id: Mapped[str] = mapped_column(String, nullable=False)
    sub_skill_id: Mapped[str] = mapped_column(ForeignKey("sub_skills.id"), nullable=False)

    p_mastery: Mapped[float] = mapped_column(Float, nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    cycle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class AttemptRecord(Base):
    """Persisted mirror of `nirelle.bkt.AttemptEvent`, linked back to the
    mastery record it was folded into.
    """

    __tablename__ = "attempt_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    class_section: Mapped[str] = mapped_column(String, nullable=False)
    mastery_record_id: Mapped[int] = mapped_column(
        ForeignKey("mastery_records.id"), nullable=False, index=True
    )

    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    misconception_tag: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class TeacherEscalation(Base):
    """The teacher-facing escalation record from the BRD's "Teacher
    escalation view": the specific misconception, what's been tried, and a
    precise summary of what to target in the 1-on-1 - not a raw data dump.
    """

    __tablename__ = "teacher_escalations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["school_id", "student_id"], ["students.school_id", "students.id"]
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    class_section: Mapped[str] = mapped_column(String, nullable=False)
    student_id: Mapped[str] = mapped_column(String, nullable=False)
    sub_skill_id: Mapped[str] = mapped_column(ForeignKey("sub_skills.id"), nullable=False)

    misconception_summary: Mapped[str] = mapped_column(Text, nullable=False)
    remediation_attempted: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    one_on_one_focus: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)


class ParentReport(Base):
    """The parent-facing view from the BRD: a separate, high-level report,
    not the full misconception-level diagnostic detail given to teachers.
    """

    __tablename__ = "parent_reports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["school_id", "student_id"], ["students.school_id", "students.id"]
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    class_section: Mapped[str] = mapped_column(String, nullable=False)
    student_id: Mapped[str] = mapped_column(String, nullable=False)
    sub_skill_id: Mapped[str] = mapped_column(ForeignKey("sub_skills.id"), nullable=False)

    plain_summary: Mapped[str] = mapped_column(Text, nullable=False)
    at_home_actions: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # newline-separated, 1-2 items per the BRD

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
