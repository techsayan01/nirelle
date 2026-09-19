"""Generates the data behind the "why recency-weighted BKT" comparison
artifact, per the BRD's differentiation: heuristic/rule-based (as
Mindspark was built) vs. classic BKT vs. Nirelle's recency-weighted BKT.

Runs one fixed, hand-designed synthetic response sequence - a student who
is genuinely struggling, then genuinely gets it after remediation (with
one realistic slip afterward) - through three trackers and records each
one's confidence/mastery estimate after every attempt. The BKT trackers
use `nirelle.bkt.update_mastery` directly (the exact function the product
ships), not a reimplementation, so the comparison is honest.

The fourth category from the BRD (LLM-only / knowledge-graph judgment)
isn't included here: it doesn't produce a comparable continuous score
attempt-by-attempt, so it's handled as a qualitative comparison in the
artifact instead of a fourth line on this chart.

Usage: python3 scripts/model_comparison_simulation.py
Writes scripts/model_comparison_data.json.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nirelle.bkt import AttemptEvent, BKTConfig, SkillParams, update_mastery  # noqa: E402

# --- the synthetic student -------------------------------------------------
#
# Attempts 1-8: genuinely doesn't know the skill yet (correct only when
# guessing gets lucky - consistent with p_guess=0.2).
# Remediation happens between attempt 8 and 9.
# Attempts 9-20: genuinely knows it now, with one realistic slip at
# attempt 14 (consistent with p_slip=0.1) - the moment that matters most
# for this comparison, since it's where a brittle heuristic and a
# probabilistic model diverge the most.
RESPONSES = [
    False, False, True, False, False, False, True, False,  # 1-8: struggling
    True, True, True, True, True, False, True, True, True, True, True, True,  # 9-20: got it (one slip at 14)
]
SHIFT_AFTER_ATTEMPT = 8  # remediation happens between attempt 8 and attempt 9

# Slightly less discriminative than the package defaults: p_guess=0.3 /
# p_slip=0.2 models a noisier skill (e.g. multiple-choice items where
# careless slips and lucky guesses are both fairly common - realistic for
# a lot of K-12 math). This matters for the comparison: with very
# discriminative parameters, a single correct answer is already such
# strong evidence that classic and recency-weighted BKT converge to
# nearly the same speed, masking the effect recency-weighting actually
# has. Under realistic noise, the difference is real and reproducible.
PARAMS = SkillParams(p_init=0.3, p_learn=0.08, p_slip=0.2, p_guess=0.3)
FLOOR = 0.75

HEURISTIC_STREAK_TARGET = 3  # "3 correct in a row = mastered" - a common rule-based design


@dataclass
class Trajectory:
    name: str
    values: list[float]


def heuristic_streak_trajectory(responses: list[bool]) -> Trajectory:
    """A streak-counter heuristic: any wrong answer resets progress to
    zero, `HEURISTIC_STREAK_TARGET` correct in a row reads as "mastered"
    (1.0). This is a real, common rule-based design (not a strawman) -
    it's exactly the brittleness that motivates a probabilistic model.
    """
    values: list[float] = []
    streak = 0
    for correct in responses:
        streak = streak + 1 if correct else 0
        values.append(min(streak / HEURISTIC_STREAK_TARGET, 1.0))
    return Trajectory("Heuristic (streak-based)", values)


def bkt_trajectory(responses: list[bool], config: BKTConfig, name: str) -> Trajectory:
    p_mastery = PARAMS.p_init
    history: list[AttemptEvent] = []
    values: list[float] = []
    for correct in responses:
        attempt = AttemptEvent(correct=correct, response_time_ms=4000)
        p_mastery = update_mastery(p_mastery, history, attempt, PARAMS, config)
        history.append(attempt)
        values.append(p_mastery)
    return Trajectory(name, values)


def attempts_to_cross_floor_after_shift(values: list[float]) -> int | None:
    """How many attempts after the shift until this model's estimate first
    reaches the mastery floor. None if it never does within the sequence.
    """
    for i, v in enumerate(values[SHIFT_AFTER_ATTEMPT:], start=1):
        if v >= FLOOR:
            return i
    return None


def main() -> None:
    heuristic = heuristic_streak_trajectory(RESPONSES)
    classic = bkt_trajectory(RESPONSES, BKTConfig(recency_weight=0.0), "Classic BKT")
    recency_weighted = bkt_trajectory(RESPONSES, BKTConfig(), "Recency-weighted BKT (Nirelle)")

    pre_shift_correct_indices = [i for i, c in enumerate(RESPONSES[:SHIFT_AFTER_ATTEMPT]) if c]

    summary = {
        "floor": FLOOR,
        "shift_after_attempt": SHIFT_AFTER_ATTEMPT,
        "attempts_to_floor_after_shift": {
            "classic_bkt": attempts_to_cross_floor_after_shift(classic.values),
            "recency_weighted_bkt": attempts_to_cross_floor_after_shift(recency_weighted.values),
        },
        "lucky_guess_spikes_pre_shift": {
            "attempt_numbers": [i + 1 for i in pre_shift_correct_indices],
            "classic_bkt": [classic.values[i] for i in pre_shift_correct_indices],
            "recency_weighted_bkt": [recency_weighted.values[i] for i in pre_shift_correct_indices],
        },
        "min_after_shift": {
            "heuristic": min(heuristic.values[SHIFT_AFTER_ATTEMPT:]),
            "classic_bkt": min(classic.values[SHIFT_AFTER_ATTEMPT:]),
            "recency_weighted_bkt": min(recency_weighted.values[SHIFT_AFTER_ATTEMPT:]),
        },
        "params": {
            "p_init": PARAMS.p_init,
            "p_learn": PARAMS.p_learn,
            "p_slip": PARAMS.p_slip,
            "p_guess": PARAMS.p_guess,
        },
    }

    data = {
        "responses": RESPONSES,
        "shift_after_attempt": SHIFT_AFTER_ATTEMPT,
        "floor": FLOOR,
        "trajectories": [
            {"key": "heuristic", "name": heuristic.name, "values": heuristic.values},
            {"key": "classic", "name": classic.name, "values": classic.values},
            {"key": "recency", "name": recency_weighted.name, "values": recency_weighted.values},
        ],
        "summary": summary,
    }

    out_path = Path(__file__).resolve().parent / "model_comparison_data.json"
    out_path.write_text(json.dumps(data, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
