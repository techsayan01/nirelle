"""Pydantic request/response models for the HTTP API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..bkt.types import LoopStage


# --- schools (tenants) -------------------------------------------------------


class SchoolCreate(BaseModel):
    id: str
    name: str


class SchoolOut(SchoolCreate):
    model_config = ConfigDict(from_attributes=True)


# --- curriculum layer --------------------------------------------------------


class SubSkillCreate(BaseModel):
    id: str
    name: str
    grade: int
    subject: str
    chapter: str
    p_init: float = 0.3
    p_learn: float = 0.15
    p_slip: float = 0.1
    p_guess: float = 0.2


class SubSkillOut(SubSkillCreate):
    model_config = ConfigDict(from_attributes=True)


class ExplanationStrategyCreate(BaseModel):
    misconception_tag: str
    content: str
    rank: int = 0


class ExplanationStrategyOut(ExplanationStrategyCreate):
    id: int
    sub_skill_id: str

    model_config = ConfigDict(from_attributes=True)


class PersonalizeRequest(BaseModel):
    strategy_id: int
    student_display_name: str
    grade: int
    tone_hint: str | None = None


class PersonalizeOut(BaseModel):
    content: str


# --- students -----------------------------------------------------------


class StudentCreate(BaseModel):
    id: str
    class_section: str
    display_name: str


class StudentOut(StudentCreate):
    school_id: str

    model_config = ConfigDict(from_attributes=True)


# --- mastery loop ---------------------------------------------------------


class AttemptIn(BaseModel):
    correct: bool
    response_time_ms: int = Field(gt=0)
    stage: LoopStage = LoopStage.DIAGNOSTIC
    misconception_tag: str | None = None


class MasteryStateOut(BaseModel):
    student_id: str
    sub_skill_id: str
    p_mastery: float
    stage: LoopStage
    cycle_count: int
    attempt_count: int
    recommended_question_count: int


# --- escalations / parent reports -------------------------------------------


class TeacherEscalationCreate(BaseModel):
    student_id: str
    sub_skill_id: str
    misconception_description: str
    remediation_strategies_tried: list[str]
    attempt_count: int
    last_mastery_score: float
    floor_mastery: float


class TeacherEscalationOut(BaseModel):
    id: int
    school_id: str
    class_section: str
    student_id: str
    sub_skill_id: str
    misconception_summary: str
    remediation_attempted: str
    attempt_count: int
    one_on_one_focus: str
    resolved_at: datetime | None = None
    resolved_by: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EscalationResolve(BaseModel):
    resolved_by: str


class ParentReportCreate(BaseModel):
    student_id: str
    sub_skill_id: str
    sub_skill_name_plain: str
    at_home_actions: list[str]


class ParentReportOut(BaseModel):
    id: int
    school_id: str
    class_section: str
    student_id: str
    sub_skill_id: str
    plain_summary: str
    at_home_actions: str

    model_config = ConfigDict(from_attributes=True)


# --- integrity ---------------------------------------------------------


class QuestionAttemptIn(BaseModel):
    correct: bool
    response_time_ms: int = Field(ge=0)
    difficulty: float = Field(ge=0.0, le=1.0)


class IntegrityCheckIn(BaseModel):
    session: list[QuestionAttemptIn]
    predicted_mastery: float = Field(ge=0.0, le=1.0)
    retest_session: list[QuestionAttemptIn] | None = None
    tab_switch_count: int | None = None


class IntegritySignalOut(BaseModel):
    name: str
    triggered: bool
    detail: str


class IntegrityAssessmentOut(BaseModel):
    flagged: bool
    signals: list[IntegritySignalOut]


# --- demo diagnostics (hand-built Grade 4 Math / Fractions content) ---------


class DemoChoiceOut(BaseModel):
    """A choice's `label` only - never the correct answer or misconception
    tag, so the client can't read the key out of the network response.
    """

    id: str
    label: str


class DemoQuestionOut(BaseModel):
    id: str
    sub_skill_id: str
    difficulty: float
    prompt: str
    choices: list[DemoChoiceOut]


class DemoResponseIn(BaseModel):
    question_id: str
    selected_choice_id: str
    response_time_ms: int = Field(gt=0)


class DemoSubmissionIn(BaseModel):
    responses: list[DemoResponseIn]


class DemoGradedResponseOut(BaseModel):
    question_id: str
    correct: bool


class DemoSubmissionOut(BaseModel):
    graded: list[DemoGradedResponseOut]
    misconception_tag: str | None
    misconception_confidence: str
