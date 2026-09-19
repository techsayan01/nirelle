"""Recency-weighted Bayesian Knowledge Tracing.

Implements the standard four-parameter BKT sequential update (Corbett &
Anderson, 1994) with a recency-weighting layer inspired by Agarwal, Baker &
Muraleedharan, "Dynamic Knowledge Tracing through Data Driven Recency
Weights" (EDM 2020):
https://educationaldatamining.org/files/conferences/EDM2020/papers/paper_8.pdf

Classic BKT folds every past attempt into a single running posterior with a
fixed learning rate, so a real shift in a student's performance (a
misconception clicking, or a lucky guessing streak) takes many attempts to
move the mastery estimate. Agarwal et al. show that weighting recent
attempts more heavily when re-estimating mastery lets the model react in
far fewer attempts, at the cost of some extra noise sensitivity.

This module does not reproduce Agarwal et al.'s specific data-fit decay
weights - those were learned by search over ASSISTments and other datasets
we don't have in front of us. Instead it implements the general mechanism
their paper is an instance of: an exponentially decayed window over recent
outcomes, blended into the BKT prior. `window`, `decay`, and
`recency_weight` are left as tunable parameters so they can be fit against
real pilot data later, per the BRD's open item to test against ASSISTments-
and Mindspark-style datasets.
"""
from __future__ import annotations

from dataclasses import dataclass

from .params import SkillParams
from .types import AttemptEvent


@dataclass(frozen=True)
class BKTConfig:
    """Tunable knobs for the recency-weighting layer.

    window:         how many of the most recent past attempts feed the
                     recency-weighted rate.
    decay:          per-step exponential decay applied going backwards from
                     the newest of those attempts; must be in (0, 1].
                     1.0 = no decay (a plain moving average over the
                     window).
    recency_weight: beta in [0, 1], blended against the long-run posterior
                     to form the prior used for the evidence step.
                     0.0 reproduces classic BKT exactly; higher values react
                     faster to recent shifts at the cost of more noise
                     sensitivity.
    """

    window: int = 5
    decay: float = 0.6
    recency_weight: float = 0.35

    def __post_init__(self) -> None:
        if self.window < 1:
            raise ValueError(f"window={self.window!r} must be >= 1")
        if not 0.0 < self.decay <= 1.0:
            raise ValueError(f"decay={self.decay!r} must be in (0, 1]")
        if not 0.0 <= self.recency_weight <= 1.0:
            raise ValueError(f"recency_weight={self.recency_weight!r} must be in [0, 1]")


DEFAULT_CONFIG = BKTConfig()


def recency_weighted_rate(
    history: list[AttemptEvent], config: BKTConfig = DEFAULT_CONFIG
) -> float | None:
    """Exponentially-decayed correctness rate over the recent past attempts.

    Only looks at ``history`` (attempts strictly before the one being
    processed), so this represents "how has the student been doing lately"
    independent of the new observation, which is folded in separately as
    Bayesian evidence. Returns ``None`` when there is no history yet.
    """
    if not history:
        return None

    window_events = history[-config.window :]
    ordered = list(reversed(window_events))  # newest first

    total_weight = 0.0
    weighted_sum = 0.0
    for i, event in enumerate(ordered):
        weight = config.decay**i
        total_weight += weight
        weighted_sum += weight * float(event.correct)

    return weighted_sum / total_weight


def _bayes_evidence_update(prior: float, correct: bool, params: SkillParams) -> float:
    """Standard BKT posterior update given one observed attempt."""
    if correct:
        p_obs_given_mastery = 1.0 - params.p_slip
        p_obs_given_not_mastery = params.p_guess
    else:
        p_obs_given_mastery = params.p_slip
        p_obs_given_not_mastery = 1.0 - params.p_guess

    numerator = prior * p_obs_given_mastery
    denominator = numerator + (1.0 - prior) * p_obs_given_not_mastery

    if denominator <= 0.0:
        # Degenerate case (e.g. p_slip=0 and an incorrect answer with
        # prior=1): the observation is impossible under the current
        # belief, so fall back to the prior rather than dividing by zero.
        return prior

    return numerator / denominator


def _transit_step(posterior: float, params: SkillParams) -> float:
    """P(L_n) after the learning opportunity, given the post-evidence posterior."""
    return posterior + (1.0 - posterior) * params.p_learn


def update_mastery(
    p_mastery: float,
    history: list[AttemptEvent],
    new_attempt: AttemptEvent,
    params: SkillParams,
    config: BKTConfig = DEFAULT_CONFIG,
) -> float:
    """Advance a mastery estimate by one attempt.

    Recency weighting is applied by blending the long-run posterior
    (``p_mastery``) with the recency-weighted rate of recent past attempts
    to form the prior fed into the Bayesian evidence step. With
    ``config.recency_weight == 0`` (or on a student's first attempt, where
    there's no history to weight) this is exactly classic BKT.
    """
    recent_rate = recency_weighted_rate(history, config)
    beta = config.recency_weight

    if beta > 0.0 and recent_rate is not None:
        effective_prior = (1.0 - beta) * p_mastery + beta * recent_rate
    else:
        effective_prior = p_mastery

    posterior = _bayes_evidence_update(effective_prior, new_attempt.correct, params)
    return _transit_step(posterior, params)
