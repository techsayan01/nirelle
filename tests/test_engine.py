from __future__ import annotations

import pytest

from nirelle import (
    AttemptEvent,
    EngineConfig,
    LoopStage,
    MasteryEngine,
    SkillParams,
)


def make_attempt(correct: bool) -> AttemptEvent:
    return AttemptEvent(correct=correct, response_time_ms=4000)


@pytest.fixture
def params() -> SkillParams:
    return SkillParams(p_init=0.3, p_learn=0.15, p_slip=0.1, p_guess=0.2)


@pytest.fixture
def engine() -> MasteryEngine:
    return MasteryEngine(engine_config=EngineConfig(floor_mastery=0.75, max_cycles=3))


def test_get_or_create_state_seeds_from_p_init(engine, params):
    state = engine.get_or_create_state("student-1", "fractions.add", params)
    assert state.p_mastery == params.p_init
    assert state.stage is LoopStage.DIAGNOSTIC
    assert state.cycle_count == 0


def test_get_or_create_state_is_idempotent(engine, params):
    first = engine.get_or_create_state("student-1", "fractions.add", params)
    first.p_mastery = 0.9  # mutate to prove the same object comes back
    second = engine.get_or_create_state("student-1", "fractions.add", params)
    assert second is first
    assert second.p_mastery == 0.9


def test_record_attempt_updates_mastery_and_appends_history(engine, params):
    state = engine.get_or_create_state("student-1", "fractions.add", params)
    engine.record_attempt(state, make_attempt(True), params)
    assert state.attempt_count == 1
    assert state.p_mastery > params.p_init


def test_decide_question_count_asks_more_when_near_floor(params):
    engine = MasteryEngine(
        engine_config=EngineConfig(floor_mastery=0.75, uncertainty_band=0.1)
    )
    state = engine.get_or_create_state("student-1", "fractions.add", params)

    state.p_mastery = 0.74  # inside the uncertainty band
    assert engine.decide_question_count(state) == 3

    state.p_mastery = 0.2  # clearly below floor
    assert engine.decide_question_count(state) == 2

    state.p_mastery = 0.95  # clearly above floor
    assert engine.decide_question_count(state) == 2


def test_evaluate_retest_resolves_when_above_floor(engine, params):
    state = engine.get_or_create_state("student-1", "fractions.add", params)
    state.p_mastery = 0.9
    engine.begin_retest(state)
    assert engine.evaluate_retest(state) is LoopStage.RESOLVED


def test_evaluate_retest_loops_back_when_below_floor_and_cycles_remain(engine, params):
    state = engine.get_or_create_state("student-1", "fractions.add", params)
    state.p_mastery = 0.4
    engine.begin_retest(state)
    result = engine.evaluate_retest(state)
    assert result is LoopStage.DIAGNOSTIC
    assert state.cycle_count == 1


def test_evaluate_retest_escalates_once_cycles_are_exhausted(params):
    engine = MasteryEngine(engine_config=EngineConfig(floor_mastery=0.75, max_cycles=2))
    state = engine.get_or_create_state("student-1", "fractions.add", params)
    state.p_mastery = 0.4

    engine.begin_retest(state)
    assert engine.evaluate_retest(state) is LoopStage.DIAGNOSTIC
    assert state.cycle_count == 1

    engine.begin_retest(state)
    assert engine.evaluate_retest(state) is LoopStage.ESCALATED
    assert state.cycle_count == 2


def test_evaluate_retest_requires_retest_stage(engine, params):
    state = engine.get_or_create_state("student-1", "fractions.add", params)
    with pytest.raises(ValueError):
        engine.evaluate_retest(state)


def test_teacher_escalation_flow_closes_the_loop_from_evidence(engine, params):
    state = engine.get_or_create_state("student-1", "fractions.add", params)
    state.stage = LoopStage.ESCALATED

    assert engine.resolve_teacher_escalation(state) is LoopStage.TEACHER_RETEST

    # System runs one more re-test after the teacher's 1-on-1.
    engine.record_attempt(state, make_attempt(True), params)
    engine.record_attempt(state, make_attempt(True), params)

    assert engine.finalize_teacher_retest(state) is LoopStage.RESOLVED


def test_finalize_teacher_retest_closes_loop_even_if_still_below_floor(engine, params):
    """Per the BRD, the post-teacher re-test only updates the score from
    evidence - it must not silently re-trigger the automated loop again.
    """
    state = engine.get_or_create_state("student-1", "fractions.add", params)
    state.stage = LoopStage.ESCALATED
    engine.resolve_teacher_escalation(state)
    state.p_mastery = 0.2  # still below floor even after the teacher stepped in

    assert engine.finalize_teacher_retest(state) is LoopStage.RESOLVED


def test_resolve_teacher_escalation_requires_escalated_stage(engine, params):
    state = engine.get_or_create_state("student-1", "fractions.add", params)
    with pytest.raises(ValueError):
        engine.resolve_teacher_escalation(state)


def test_finalize_teacher_retest_requires_teacher_retest_stage(engine, params):
    state = engine.get_or_create_state("student-1", "fractions.add", params)
    with pytest.raises(ValueError):
        engine.finalize_teacher_retest(state)


def test_engine_config_rejects_out_of_range_values():
    with pytest.raises(ValueError):
        EngineConfig(floor_mastery=0.0)
    with pytest.raises(ValueError):
        EngineConfig(max_cycles=0)
    with pytest.raises(ValueError):
        EngineConfig(uncertainty_band=-0.1)


def test_full_loop_to_escalation_and_teacher_resolution(params):
    """End-to-end smoke test tracing the whole BRD flowchart for a student
    who never clears the floor on their own.
    """
    engine = MasteryEngine(engine_config=EngineConfig(floor_mastery=0.9, max_cycles=2))
    state = engine.get_or_create_state("student-1", "fractions.add", params)

    for _ in range(engine._engine_config.max_cycles):
        assert state.stage is LoopStage.DIAGNOSTIC
        engine.record_attempt(state, make_attempt(False), params)
        engine.begin_remediation(state)
        engine.begin_retest(state)
        engine.record_attempt(state, make_attempt(False), params)
        engine.evaluate_retest(state)

    assert state.stage is LoopStage.ESCALATED

    engine.resolve_teacher_escalation(state)
    engine.record_attempt(state, make_attempt(True), params)
    final_stage = engine.finalize_teacher_retest(state)

    assert final_stage is LoopStage.RESOLVED
