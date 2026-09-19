"""Mastery engine: recency-weighted BKT plus the diagnose -> remediate ->
re-test -> escalate loop from the Nirelle BRD's "Product scope: the
remediation loop" section.

Curriculum-layer concerns - which explanation strategy to serve for a
misconception, question content/selection, the LLM personalization layer -
live outside this engine. It only owns the mastery number and the loop
state machine that decides when to remediate, re-test, or escalate to the
teacher.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import DEFAULT_CONFIG, BKTConfig, update_mastery
from .params import SkillParams
from .types import AttemptEvent, LoopStage, MasteryState


@dataclass(frozen=True)
class EngineConfig:
    """Policy knobs for the remediation loop, separate from the BKT math.

    floor_mastery:    the minimum-mastery bar from the BRD's problem
                       statement; at or above this, a case is resolved.
    max_cycles:       diagnose-remediate-re-test cycles allowed before
                       escalation ("2-3 cycles" per the BRD).
    uncertainty_band: distance from the floor within which the engine
                       treats mastery as too close to call, asking for a
                       third diagnostic/re-test question instead of two.
    """

    floor_mastery: float = 0.75
    max_cycles: int = 3
    uncertainty_band: float = 0.1

    def __post_init__(self) -> None:
        if not 0.0 < self.floor_mastery <= 1.0:
            raise ValueError(f"floor_mastery={self.floor_mastery!r} must be in (0, 1]")
        if self.max_cycles < 1:
            raise ValueError(f"max_cycles={self.max_cycles!r} must be >= 1")
        if not 0.0 <= self.uncertainty_band <= 1.0:
            raise ValueError(
                f"uncertainty_band={self.uncertainty_band!r} must be in [0, 1]"
            )


DEFAULT_ENGINE_CONFIG = EngineConfig()


class MasteryEngine:
    """Owns per-(student, sub-skill) mastery state and the remediation loop."""

    def __init__(
        self,
        bkt_config: BKTConfig = DEFAULT_CONFIG,
        engine_config: EngineConfig = DEFAULT_ENGINE_CONFIG,
    ) -> None:
        self._bkt_config = bkt_config
        self._engine_config = engine_config
        self._states: dict[tuple[str, str], MasteryState] = {}

    def get_or_create_state(
        self, student_id: str, sub_skill_id: str, params: SkillParams
    ) -> MasteryState:
        key = (student_id, sub_skill_id)
        state = self._states.get(key)
        if state is None:
            state = MasteryState(
                student_id=student_id,
                sub_skill_id=sub_skill_id,
                p_mastery=params.p_init,
            )
            self._states[key] = state
        return state

    def record_attempt(
        self, state: MasteryState, attempt: AttemptEvent, params: SkillParams
    ) -> MasteryState:
        """Fold one answered question into the mastery estimate."""
        state.p_mastery = update_mastery(
            state.p_mastery, state.history, attempt, params, self._bkt_config
        )
        state.history.append(attempt)
        return state

    def decide_question_count(self, state: MasteryState) -> int:
        """2 or 3 diagnostic/re-test questions, per how close mastery sits
        to the floor: near the decision boundary asks one more question
        before committing to a stage transition.
        """
        distance = abs(state.p_mastery - self._engine_config.floor_mastery)
        return 3 if distance <= self._engine_config.uncertainty_band else 2

    def is_above_floor(self, state: MasteryState) -> bool:
        return state.p_mastery >= self._engine_config.floor_mastery

    def begin_remediation(self, state: MasteryState) -> LoopStage:
        state.stage = LoopStage.REMEDIATION
        return state.stage

    def begin_retest(self, state: MasteryState) -> LoopStage:
        state.stage = LoopStage.RETEST
        return state.stage

    def evaluate_retest(self, state: MasteryState) -> LoopStage:
        """Advance the loop after a re-test, per the BRD flow: floor
        reached -> resolved; still below floor with cycles left -> back to
        diagnostic; cycles exhausted -> escalate to the teacher.
        """
        if state.stage is not LoopStage.RETEST:
            raise ValueError(
                f"evaluate_retest() called on stage={state.stage!r}, "
                "expected LoopStage.RETEST"
            )

        if self.is_above_floor(state):
            state.stage = LoopStage.RESOLVED
            return state.stage

        state.cycle_count += 1
        if state.cycle_count >= self._engine_config.max_cycles:
            state.stage = LoopStage.ESCALATED
        else:
            state.stage = LoopStage.DIAGNOSTIC
        return state.stage

    def resolve_teacher_escalation(self, state: MasteryState) -> LoopStage:
        """Teacher marks the case resolved. Per the BRD this triggers one
        automatic re-test so the mastery score updates from evidence, not
        the teacher's say-so. Caller records that re-test's attempt(s) via
        record_attempt(), then calls finalize_teacher_retest().
        """
        if state.stage is not LoopStage.ESCALATED:
            raise ValueError(
                f"resolve_teacher_escalation() called on stage={state.stage!r}, "
                "expected LoopStage.ESCALATED"
            )
        state.stage = LoopStage.TEACHER_RETEST
        return state.stage

    def finalize_teacher_retest(self, state: MasteryState) -> LoopStage:
        """Close the loop after the teacher-triggered re-test. Per the BRD
        this step only updates the mastery score from evidence - it does
        not re-enter the automated escalation loop even if the score still
        sits below floor, since the teacher has already intervened.
        """
        if state.stage is not LoopStage.TEACHER_RETEST:
            raise ValueError(
                f"finalize_teacher_retest() called on stage={state.stage!r}, "
                "expected LoopStage.TEACHER_RETEST"
            )
        state.stage = LoopStage.RESOLVED
        return state.stage
