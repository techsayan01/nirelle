from __future__ import annotations

import pytest

from nirelle.integrity import (
    IntegrityConfig,
    QuestionAttempt,
    SignalName,
    assess_session,
    detect_answer_pattern_mismatch,
    detect_focus_loss,
    detect_mastery_prediction_mismatch,
    detect_response_time_outlier,
)


def qa(correct: bool, response_time_ms: int, difficulty: float) -> QuestionAttempt:
    return QuestionAttempt(correct=correct, response_time_ms=response_time_ms, difficulty=difficulty)


# --- Signal 1: response-time outliers -------------------------------------


def test_response_time_outlier_flags_fast_correct_answer_on_hard_question():
    session = [qa(True, 1500, difficulty=0.9)]
    signal = detect_response_time_outlier(session)
    assert signal.name is SignalName.RESPONSE_TIME_OUTLIER
    assert signal.triggered


def test_response_time_outlier_does_not_flag_fast_wrong_answer_on_hard_question():
    # Fast + hard + wrong isn't suspicious the same way - a guess that missed.
    session = [qa(False, 1500, difficulty=0.9)]
    signal = detect_response_time_outlier(session)
    assert not signal.triggered


def test_response_time_outlier_does_not_flag_fast_answer_on_easy_question():
    session = [qa(True, 1500, difficulty=0.2)]
    assert not detect_response_time_outlier(session).triggered


def test_response_time_outlier_flags_erratic_fast_slow_fast_pattern():
    session = [
        qa(True, 1000, difficulty=0.5),
        qa(True, 9000, difficulty=0.5),
        qa(True, 1000, difficulty=0.5),
        qa(True, 9000, difficulty=0.5),
    ]
    signal = detect_response_time_outlier(session)
    assert signal.triggered


def test_response_time_outlier_does_not_flag_smoothly_drifting_times():
    session = [
        qa(True, 4000, difficulty=0.5),
        qa(True, 4500, difficulty=0.5),
        qa(True, 5000, difficulty=0.5),
        qa(True, 5500, difficulty=0.5),
    ]
    assert not detect_response_time_outlier(session).triggered


def test_response_time_outlier_not_flagged_from_raw_response_time_alone():
    # Single fast-but-easy attempt: never decisive on its own.
    session = [qa(True, 500, difficulty=0.1)]
    assert not detect_response_time_outlier(session).triggered


# --- Signal 2: answer-pattern-vs-difficulty mismatch -----------------------


def test_answer_pattern_mismatch_flags_acing_hard_missing_easy():
    session = [
        qa(True, 5000, difficulty=0.9),
        qa(True, 5000, difficulty=0.85),
        qa(False, 5000, difficulty=0.2),
        qa(False, 5000, difficulty=0.15),
    ]
    signal = detect_answer_pattern_mismatch(session)
    assert signal.triggered


def test_answer_pattern_mismatch_not_flagged_when_performance_matches_difficulty():
    session = [
        qa(False, 5000, difficulty=0.9),
        qa(False, 5000, difficulty=0.85),
        qa(True, 5000, difficulty=0.2),
        qa(True, 5000, difficulty=0.15),
    ]
    assert not detect_answer_pattern_mismatch(session).triggered


def test_answer_pattern_mismatch_not_flagged_with_insufficient_samples():
    session = [qa(True, 5000, difficulty=0.9), qa(False, 5000, difficulty=0.2)]
    signal = detect_answer_pattern_mismatch(
        session, IntegrityConfig(min_questions_per_bucket=2)
    )
    assert not signal.triggered


# --- Signal 3: focus loss ---------------------------------------------------


def test_focus_loss_not_flagged_when_uninstrumented():
    signal = detect_focus_loss(None)
    assert not signal.triggered


def test_focus_loss_flagged_on_any_tab_switch():
    signal = detect_focus_loss(1)
    assert signal.triggered


def test_focus_loss_not_flagged_with_zero_switches():
    signal = detect_focus_loss(0)
    assert not signal.triggered


# --- Signal 4: mastery-prediction mismatch ----------------------------------


def test_mastery_prediction_mismatch_flags_low_prediction_with_fast_ace():
    retest = [qa(True, 1000, difficulty=0.5) for _ in range(4)]
    signal = detect_mastery_prediction_mismatch(predicted_mastery=0.3, retest_session=retest)
    assert signal.triggered


def test_mastery_prediction_mismatch_not_flagged_when_ace_has_typical_timing():
    retest = [qa(True, 5000, difficulty=0.5) for _ in range(4)]
    signal = detect_mastery_prediction_mismatch(predicted_mastery=0.3, retest_session=retest)
    assert not signal.triggered


def test_mastery_prediction_mismatch_not_flagged_when_prediction_was_high():
    retest = [qa(True, 1000, difficulty=0.5) for _ in range(4)]
    signal = detect_mastery_prediction_mismatch(predicted_mastery=0.9, retest_session=retest)
    assert not signal.triggered


def test_mastery_prediction_mismatch_not_flagged_with_no_retest_data():
    signal = detect_mastery_prediction_mismatch(predicted_mastery=0.2, retest_session=[])
    assert not signal.triggered


# --- Composite assessment ---------------------------------------------------


def test_assess_session_not_flagged_with_only_one_signal_triggered():
    # Only focus-loss fires; everything else is clean.
    session = [qa(True, 5000, difficulty=0.5) for _ in range(4)]
    assessment = assess_session(
        session, predicted_mastery=0.9, tab_switch_count=1
    )
    assert len(assessment.triggered_signals) == 1
    assert not assessment.flagged


def test_assess_session_flagged_when_two_signals_trigger():
    session = [
        qa(True, 1500, difficulty=0.9),  # fast+hard -> response_time_outlier
        qa(True, 1500, difficulty=0.85),
        qa(False, 5000, difficulty=0.2),  # missing easy -> pattern mismatch
        qa(False, 5000, difficulty=0.15),
    ]
    assessment = assess_session(session, predicted_mastery=0.9, tab_switch_count=0)
    assert assessment.flagged
    triggered_names = {s.name for s in assessment.triggered_signals}
    assert SignalName.RESPONSE_TIME_OUTLIER in triggered_names
    assert SignalName.ANSWER_PATTERN_MISMATCH in triggered_names


def test_assess_session_returns_all_four_signals_regardless_of_outcome():
    session = [qa(True, 5000, difficulty=0.5) for _ in range(4)]
    assessment = assess_session(session, predicted_mastery=0.9)
    assert {s.name for s in assessment.signals} == set(SignalName)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"hard_difficulty_threshold": 1.5},
        {"easy_difficulty_threshold": 0.8, "hard_difficulty_threshold": 0.5},
        {"suspiciously_fast_ms": -1},
        {"min_questions_per_bucket": 0},
        {"min_triggered_for_flag": 0},
    ],
)
def test_integrity_config_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        IntegrityConfig(**kwargs)
