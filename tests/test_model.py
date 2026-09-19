from __future__ import annotations

import pytest

from nirelle import AttemptEvent, BKTConfig, SkillParams, update_mastery
from nirelle.bkt.model import _bayes_evidence_update, _transit_step, recency_weighted_rate


def make_attempt(correct: bool) -> AttemptEvent:
    return AttemptEvent(correct=correct, response_time_ms=5000)


def test_classic_bkt_matches_manual_calculation_when_recency_weight_is_zero():
    params = SkillParams(p_init=0.3, p_learn=0.15, p_slip=0.1, p_guess=0.2)
    config = BKTConfig(recency_weight=0.0)

    p_mastery = params.p_init
    posterior = _bayes_evidence_update(p_mastery, True, params)
    expected = _transit_step(posterior, params)

    actual = update_mastery(p_mastery, [], make_attempt(True), params, config)

    assert actual == pytest.approx(expected)


def test_correct_answer_increases_mastery():
    params = SkillParams()
    config = BKTConfig(recency_weight=0.0)
    updated = update_mastery(params.p_init, [], make_attempt(True), params, config)
    assert updated > params.p_init


def test_incorrect_answer_decreases_posterior_before_transit():
    params = SkillParams(p_learn=0.0)  # isolate the evidence step
    config = BKTConfig(recency_weight=0.0)
    updated = update_mastery(0.5, [], make_attempt(False), params, config)
    assert updated < 0.5


def test_mastery_stays_within_unit_interval_over_many_updates():
    params = SkillParams()
    config = BKTConfig()
    p_mastery = params.p_init
    history: list[AttemptEvent] = []
    outcomes = [True, True, False, True, False, False, True, True, True, False]
    for correct in outcomes:
        attempt = make_attempt(correct)
        p_mastery = update_mastery(p_mastery, history, attempt, params, config)
        history.append(attempt)
        assert 0.0 <= p_mastery <= 1.0


def test_recency_weighting_reacts_faster_to_a_recent_wrong_streak():
    """A student who *was* doing well but has just gone cold should drop
    faster under recency weighting than under classic BKT, since the
    recent-window rate pulls the effective prior down before the new
    (also incorrect) answer is even applied as evidence.
    """
    params = SkillParams()
    p_mastery = 0.8  # long-run posterior still reads "doing well"
    recent_wrong_streak = [make_attempt(False), make_attempt(False), make_attempt(False)]
    new_attempt = make_attempt(False)

    classic = update_mastery(
        p_mastery, recent_wrong_streak, new_attempt, params, BKTConfig(recency_weight=0.0)
    )
    recency_weighted = update_mastery(
        p_mastery, recent_wrong_streak, new_attempt, params, BKTConfig(recency_weight=0.5)
    )

    assert recency_weighted < classic


def test_recency_weighting_reacts_faster_to_a_recent_correct_streak():
    params = SkillParams()
    p_mastery = 0.3  # long-run posterior still reads "struggling"
    recent_correct_streak = [make_attempt(True), make_attempt(True), make_attempt(True)]
    new_attempt = make_attempt(True)

    classic = update_mastery(
        p_mastery, recent_correct_streak, new_attempt, params, BKTConfig(recency_weight=0.0)
    )
    recency_weighted = update_mastery(
        p_mastery, recent_correct_streak, new_attempt, params, BKTConfig(recency_weight=0.5)
    )

    assert recency_weighted > classic


def test_recency_weighted_rate_is_none_with_no_history():
    assert recency_weighted_rate([]) is None


def test_recency_weighted_rate_weights_newest_attempt_most():
    history = [make_attempt(False), make_attempt(False), make_attempt(True)]
    rate = recency_weighted_rate(history, BKTConfig(decay=0.5, window=3))
    # newest (correct) attempt dominates: rate should sit above 1/3 (the
    # unweighted average of one correct out of three).
    assert rate > 1 / 3


def test_recency_weighted_rate_respects_window_size():
    history = [make_attempt(True)] * 10
    rate = recency_weighted_rate(history, BKTConfig(window=3))
    assert rate == pytest.approx(1.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"window": 0},
        {"decay": 0.0},
        {"decay": 1.5},
        {"recency_weight": -0.1},
        {"recency_weight": 1.1},
    ],
)
def test_bkt_config_rejects_out_of_range_values(kwargs):
    with pytest.raises(ValueError):
        BKTConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"p_init": -0.1},
        {"p_learn": 1.1},
        {"p_slip": -0.5},
        {"p_guess": 2.0},
    ],
)
def test_skill_params_rejects_out_of_range_values(kwargs):
    with pytest.raises(ValueError):
        SkillParams(**kwargs)
