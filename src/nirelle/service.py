"""Orchestration layer: wires the BKT engine and persistence together into
request-sized operations. `nirelle.api` is a thin HTTP wrapper around this
module - every operation here is independently unit-testable without an
HTTP client.

`MasteryEngine` keeps a per-instance in-memory cache of states, which
suits a single long-lived process. A server handling requests across
workers/restarts needs the database as the source of truth instead, so
`RemediationService` builds a fresh, stateless `MasteryEngine` per call and
always loads/saves `MasteryState` through the `TenantRepository` - the
engine's methods all take `state` explicitly, so they work equally well
against a DB-backed state as an in-memory one.
"""
from __future__ import annotations

from .bkt import (
    DEFAULT_ENGINE_CONFIG,
    AttemptEvent,
    BKTConfig,
    EngineConfig,
    MasteryEngine,
    MasteryState,
    SkillParams,
)
from .bkt import DEFAULT_CONFIG as DEFAULT_BKT_CONFIG
from .db import CurriculumRepository, TenantRepository, models


class NotFoundError(Exception):
    """Raised for an unknown student or sub-skill - distinct from
    `ValueError`, which `MasteryEngine` raises for an invalid stage
    transition, so API callers can map the two to different status codes.
    """


def _params_from_row(row: models.SubSkill) -> SkillParams:
    return SkillParams(p_init=row.p_init, p_learn=row.p_learn, p_slip=row.p_slip, p_guess=row.p_guess)


class RemediationService:
    """Per-request/transaction facade over one school's data."""

    def __init__(
        self,
        tenant_repo: TenantRepository,
        curriculum_repo: CurriculumRepository,
        bkt_config: BKTConfig = DEFAULT_BKT_CONFIG,
        engine_config: EngineConfig = DEFAULT_ENGINE_CONFIG,
    ) -> None:
        self._repo = tenant_repo
        self._curriculum = curriculum_repo
        self._engine = MasteryEngine(bkt_config, engine_config)

    def _class_section(self, student_id: str) -> str:
        student = self._repo.get_student(student_id)
        if student is None:
            raise NotFoundError(
                f"unknown student_id={student_id!r} for school_id={self._repo.school_id!r}"
            )
        return student.class_section

    def _params(self, sub_skill_id: str) -> SkillParams:
        row = self._curriculum.get_sub_skill(sub_skill_id)
        if row is None:
            raise NotFoundError(f"unknown sub_skill_id={sub_skill_id!r}")
        return _params_from_row(row)

    def decide_question_count(self, state: MasteryState) -> int:
        return self._engine.decide_question_count(state)

    def is_above_floor(self, state: MasteryState) -> bool:
        return self._engine.is_above_floor(state)

    def get_or_create_state(self, student_id: str, sub_skill_id: str) -> MasteryState:
        state = self._repo.load_mastery_state(student_id, sub_skill_id)
        if state is not None:
            return state

        params = self._params(sub_skill_id)
        class_section = self._class_section(student_id)
        state = MasteryState(student_id=student_id, sub_skill_id=sub_skill_id, p_mastery=params.p_init)
        self._repo.save_mastery_state(state, class_section)
        return state

    def record_attempt(
        self, student_id: str, sub_skill_id: str, attempt: AttemptEvent
    ) -> MasteryState:
        state = self.get_or_create_state(student_id, sub_skill_id)
        params = self._params(sub_skill_id)
        self._engine.record_attempt(state, attempt, params)

        class_section = self._class_section(student_id)
        record = self._repo.save_mastery_state(state, class_section)
        self._repo.record_attempt(record, attempt)
        return state

    def _transition(self, student_id: str, sub_skill_id: str, apply) -> MasteryState:
        state = self.get_or_create_state(student_id, sub_skill_id)
        apply(state)
        self._repo.save_mastery_state(state, self._class_section(student_id))
        return state

    def begin_remediation(self, student_id: str, sub_skill_id: str) -> MasteryState:
        return self._transition(student_id, sub_skill_id, self._engine.begin_remediation)

    def begin_retest(self, student_id: str, sub_skill_id: str) -> MasteryState:
        return self._transition(student_id, sub_skill_id, self._engine.begin_retest)

    def evaluate_retest(self, student_id: str, sub_skill_id: str) -> MasteryState:
        return self._transition(student_id, sub_skill_id, self._engine.evaluate_retest)

    def resolve_teacher_escalation(self, student_id: str, sub_skill_id: str) -> MasteryState:
        return self._transition(student_id, sub_skill_id, self._engine.resolve_teacher_escalation)

    def finalize_teacher_retest(self, student_id: str, sub_skill_id: str) -> MasteryState:
        return self._transition(student_id, sub_skill_id, self._engine.finalize_teacher_retest)
