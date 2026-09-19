"""Anti-cheating / integrity signal detectors, per the BRD's
"Anti-cheating / integrity requirements" section:

    No single signal is decisive on its own; the system combines four:
    1. Response-time outliers
    2. Answer-pattern-vs-difficulty mismatch
    3. Browser focus-loss / tab-switch detection
    4. Mastery-prediction mismatch

``assess_session`` runs all four and only flags a session once at least
``config.min_triggered_for_flag`` of them fire together.
"""
from __future__ import annotations

from .config import IntegrityConfig
from .types import IntegrityAssessment, IntegritySignal, QuestionAttempt, SignalName

DEFAULT_CONFIG = IntegrityConfig()


def _is_erratic_timing(session: list[QuestionAttempt], config: IntegrityConfig) -> bool:
    """True when response times swing fast/slow/fast rather than drifting
    smoothly - a run of alternating-sign deltas over the session.
    """
    if len(session) < 3:
        return False

    times = [a.response_time_ms for a in session]
    deltas = [times[i + 1] - times[i] for i in range(len(times) - 1)]
    comparable_pairs = [
        (deltas[i], deltas[i + 1])
        for i in range(len(deltas) - 1)
        if deltas[i] != 0 and deltas[i + 1] != 0
    ]
    if not comparable_pairs:
        return False

    reversals = sum(1 for a, b in comparable_pairs if (a > 0) != (b > 0))
    return (reversals / len(comparable_pairs)) >= config.erratic_reversal_ratio


def detect_response_time_outlier(
    session: list[QuestionAttempt], config: IntegrityConfig = DEFAULT_CONFIG
) -> IntegritySignal:
    """Flags a suspiciously fast correct answer on a hard question, or an
    erratic fast/slow/fast timing pattern across the session - never raw
    response time alone.
    """
    fast_on_hard = [
        a
        for a in session
        if a.correct
        and a.difficulty >= config.hard_difficulty_threshold
        and a.response_time_ms < config.suspiciously_fast_ms
    ]
    if fast_on_hard:
        return IntegritySignal(
            name=SignalName.RESPONSE_TIME_OUTLIER,
            triggered=True,
            detail=(
                f"{len(fast_on_hard)} hard question(s) answered correctly in "
                f"under {config.suspiciously_fast_ms}ms"
            ),
        )

    if _is_erratic_timing(session, config):
        return IntegritySignal(
            name=SignalName.RESPONSE_TIME_OUTLIER,
            triggered=True,
            detail="response times swing fast/slow/fast across the session",
        )

    return IntegritySignal(
        name=SignalName.RESPONSE_TIME_OUTLIER,
        triggered=False,
        detail="response times unremarkable",
    )


def detect_answer_pattern_mismatch(
    session: list[QuestionAttempt], config: IntegrityConfig = DEFAULT_CONFIG
) -> IntegritySignal:
    """Flags acing hard questions while missing easy ones in the same
    session - the inverted difficulty/performance curve you'd expect from
    an outside source rather than genuine ability.
    """
    hard = [a for a in session if a.difficulty >= config.hard_difficulty_threshold]
    easy = [a for a in session if a.difficulty <= config.easy_difficulty_threshold]

    if len(hard) < config.min_questions_per_bucket or len(easy) < config.min_questions_per_bucket:
        return IntegritySignal(
            name=SignalName.ANSWER_PATTERN_MISMATCH,
            triggered=False,
            detail="not enough easy/hard questions in this session to compare",
        )

    hard_rate = sum(a.correct for a in hard) / len(hard)
    easy_rate = sum(a.correct for a in easy) / len(easy)
    gap = hard_rate - easy_rate

    if gap >= config.pattern_mismatch_gap:
        return IntegritySignal(
            name=SignalName.ANSWER_PATTERN_MISMATCH,
            triggered=True,
            detail=(
                f"hard-question correct rate ({hard_rate:.0%}) exceeds easy-question "
                f"rate ({easy_rate:.0%}) by {gap:.0%}"
            ),
        )

    return IntegritySignal(
        name=SignalName.ANSWER_PATTERN_MISMATCH,
        triggered=False,
        detail=f"hard/easy correct rates consistent (hard={hard_rate:.0%}, easy={easy_rate:.0%})",
    )


def detect_focus_loss(tab_switch_count: int | None) -> IntegritySignal:
    """A hard signal when the product is a web app: any detected
    tab-switch / focus-loss event during a session triggers it.
    ``tab_switch_count=None`` means this session wasn't instrumented for
    it (e.g. a non-web client), which is not the same as "no focus loss".
    """
    if tab_switch_count is None:
        return IntegritySignal(
            name=SignalName.FOCUS_LOSS,
            triggered=False,
            detail="session was not instrumented for focus-loss detection",
        )
    if tab_switch_count > 0:
        return IntegritySignal(
            name=SignalName.FOCUS_LOSS,
            triggered=True,
            detail=f"{tab_switch_count} tab-switch/focus-loss event(s) detected",
        )
    return IntegritySignal(
        name=SignalName.FOCUS_LOSS, triggered=False, detail="no focus loss detected"
    )


def detect_mastery_prediction_mismatch(
    predicted_mastery: float,
    retest_session: list[QuestionAttempt],
    config: IntegrityConfig = DEFAULT_CONFIG,
) -> IntegritySignal:
    """Flags the BKT engine predicting low mastery while the student aces
    the re-test with atypical timing. The divergence itself is the flag,
    not the ace alone - a genuinely well-timed ace after real remediation
    is the system working as intended.
    """
    if not retest_session:
        return IntegritySignal(
            name=SignalName.MASTERY_PREDICTION_MISMATCH,
            triggered=False,
            detail="no re-test attempts to compare against the predicted mastery",
        )

    correct_rate = sum(a.correct for a in retest_session) / len(retest_session)
    avg_response_ms = sum(a.response_time_ms for a in retest_session) / len(retest_session)

    predicted_low = predicted_mastery < config.low_mastery_threshold
    aced_it = correct_rate >= config.high_retest_correct_rate
    atypical_timing = avg_response_ms < config.atypical_fast_ms or _is_erratic_timing(
        retest_session, config
    )

    if predicted_low and aced_it and atypical_timing:
        return IntegritySignal(
            name=SignalName.MASTERY_PREDICTION_MISMATCH,
            triggered=True,
            detail=(
                f"predicted mastery {predicted_mastery:.0%} but re-test correct rate "
                f"{correct_rate:.0%} with atypical timing"
            ),
        )

    return IntegritySignal(
        name=SignalName.MASTERY_PREDICTION_MISMATCH,
        triggered=False,
        detail="re-test performance is consistent with the predicted mastery",
    )


def assess_session(
    session: list[QuestionAttempt],
    predicted_mastery: float,
    retest_session: list[QuestionAttempt] | None = None,
    tab_switch_count: int | None = None,
    config: IntegrityConfig = DEFAULT_CONFIG,
) -> IntegrityAssessment:
    """Run all four signals and combine them into one verdict.

    ``retest_session`` defaults to ``session`` when a caller doesn't
    distinguish the diagnostic session from the re-test (e.g. assessing a
    single session in isolation).
    """
    signals = (
        detect_response_time_outlier(session, config),
        detect_answer_pattern_mismatch(session, config),
        detect_focus_loss(tab_switch_count),
        detect_mastery_prediction_mismatch(
            predicted_mastery, retest_session if retest_session is not None else session, config
        ),
    )
    return IntegrityAssessment(signals=signals, min_triggered=config.min_triggered_for_flag)
