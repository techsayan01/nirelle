"""Generates the data behind the "why recency-weighted BKT" comparison
artifact, per the BRD's differentiation: heuristic/rule-based (as
Mindspark was built) vs. classic BKT vs. Nirelle's recency-weighted BKT.

Rather than one hand-picked anecdote, this runs a small BATTERY of
synthetic response sequences, each representing a different real
classroom situation, and checks whether recency-weighting's advantage
holds up across all of them - including scenarios where it's expected
to show little or no benefit, and one scenario that specifically checks
for a plausible tradeoff (noise sensitivity). All BKT trajectories use
`nirelle.bkt.update_mastery` directly (the exact function the product
ships), not a reimplementation.

Scenarios:
    remediation_click  - struggling, then genuinely improves after
                          remediation (the "does it catch mastery faster"
                          case).
    silent_regression   - doing fine, then genuinely starts struggling
                          (the symmetric "does it catch a decline faster"
                          case - just as relevant to "catch it before the
                          test" as the improvement case).
    gradual_learning    - steady, smooth improvement with no discrete
                          shift (a check that recency-weighting doesn't
                          manufacture a large difference where there's
                          nothing sudden to react to).
    noisy_plateau       - no real learning, performance oscillates around
                          a fixed ability level (an honest check for the
                          tradeoff: does weighting recent attempts more
                          heavily make the estimate more volatile when
                          the "recent trend" is just noise?).

The fourth BRD category (LLM-only / knowledge-graph judgment) isn't
included here: it doesn't produce a comparable continuous score
attempt-by-attempt, so it's handled as a qualitative comparison in the
artifact instead of a fifth trajectory.

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

# Slightly less discriminative than the package defaults: p_guess=0.3 /
# p_slip=0.2 models a noisier skill (e.g. multiple-choice items where
# careless slips and lucky guesses are both fairly common - realistic for
# a lot of K-12 math). This matters: with very discriminative parameters,
# a single correct answer is already such strong evidence that classic
# and recency-weighted BKT converge to nearly the same speed, masking the
# effect recency-weighting actually has.
PARAMS = SkillParams(p_init=0.3, p_learn=0.08, p_slip=0.2, p_guess=0.3)
FLOOR = 0.75
HEURISTIC_STREAK_TARGET = 3  # "3 correct in a row = mastered" - a common rule-based design
DEFAULT_RECENCY_WEIGHT = BKTConfig().recency_weight


@dataclass(frozen=True)
class Scenario:
    key: str
    name: str
    description: str
    responses: list[bool]
    shift_after: int | None  # None = no discrete event (gradual/noisy scenarios)
    metric: str  # "floor_cross_up" | "floor_drop_down" | "max_abs_diff" | "volatility"


SCENARIOS = [
    Scenario(
        key="remediation_click",
        name="Remediation clicks",
        description=(
            "Genuinely struggling for 8 attempts, then genuinely gets it after remediation, "
            "with one realistic slip afterward."
        ),
        responses=[
            False, False, True, False, False, False, True, False,
            True, True, True, True, True, False, True, True, True, True, True, True,
        ],
        shift_after=8,
        metric="floor_cross_up",
    ),
    Scenario(
        key="silent_regression",
        name="Silent regression",
        description=(
            "Doing fine for 8 attempts, then genuinely starts struggling - forgetting, fatigue, "
            "or a harder related concept bleeding in. The mirror image of remediation clicking."
        ),
        responses=[
            True, True, False, True, True, True, False, True,
            False, False, False, False, False, True, False, False, False, False, False, False,
        ],
        shift_after=8,
        metric="floor_drop_down",
    ),
    Scenario(
        key="gradual_learning",
        name="Gradual, steady learning",
        description=(
            "No sudden shift anywhere - correctness density climbs smoothly across all 20 "
            "attempts instead of jumping at one point."
        ),
        responses=[
            False, False, True, False, False,
            False, True, False, True, False,
            True, False, True, True, True,
            True, True, False, True, True,
        ],
        shift_after=None,
        metric="max_abs_diff",
    ),
    Scenario(
        key="noisy_plateau",
        name="Noisy plateau",
        description=(
            "No real learning happening - correctness oscillates around the same ~50% ability "
            "level for all 20 attempts, no trend in either direction."
        ),
        responses=[
            True, False, False, True, True, False, True, False, False, True,
            True, False, False, True, True, False, True, False, True, False,
        ],
        shift_after=None,
        metric="volatility",
    ),
]

# The first re-test checkpoint after remediation: MasteryEngine.evaluate_retest()
# only runs after a batch of re-test questions (2 or 3, per
# decide_question_count()), not after every single attempt - 2 is the
# representative/common case, so this checkpoint is where classic and
# recency-weighted BKT's *decisions*, not just their numbers, can diverge.
CHECKPOINT_OFFSET = 2


def heuristic_streak_trajectory(responses: list[bool]) -> list[float]:
    """A streak-counter heuristic: any wrong answer resets progress to
    zero, `HEURISTIC_STREAK_TARGET` correct in a row reads as "mastered"
    (1.0). A real, common rule-based design, not a strawman.
    """
    values: list[float] = []
    streak = 0
    for correct in responses:
        streak = streak + 1 if correct else 0
        values.append(min(streak / HEURISTIC_STREAK_TARGET, 1.0))
    return values


def bkt_trajectory(responses: list[bool], config: BKTConfig) -> list[float]:
    p_mastery = PARAMS.p_init
    history: list[AttemptEvent] = []
    values: list[float] = []
    for correct in responses:
        attempt = AttemptEvent(correct=correct, response_time_ms=4000)
        p_mastery = update_mastery(p_mastery, history, attempt, PARAMS, config)
        history.append(attempt)
        values.append(p_mastery)
    return values


def attempts_to_cross_floor_after(values: list[float], shift_after: int, floor: float = FLOOR) -> int | None:
    for i, v in enumerate(values[shift_after:], start=1):
        if v >= floor:
            return i
    return None


def attempts_to_drop_below_floor_after(values: list[float], shift_after: int, floor: float = FLOOR) -> int | None:
    for i, v in enumerate(values[shift_after:], start=1):
        if v < floor:
            return i
    return None


def max_abs_diff(a: list[float], b: list[float]) -> float:
    return max(abs(x - y) for x, y in zip(a, b))


def volatility_stats(values: list[float]) -> dict:
    diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return {
        "max_abs_step": max(abs(d) for d in diffs),
        "stdev": variance**0.5,
    }


def analyze_scenario(scenario: Scenario) -> dict:
    heuristic = heuristic_streak_trajectory(scenario.responses)
    classic = bkt_trajectory(scenario.responses, BKTConfig(recency_weight=0.0))
    recency = bkt_trajectory(scenario.responses, BKTConfig())

    finding: dict
    if scenario.metric == "floor_cross_up":
        finding = {
            "type": scenario.metric,
            "classic_attempts": attempts_to_cross_floor_after(classic, scenario.shift_after),
            "recency_attempts": attempts_to_cross_floor_after(recency, scenario.shift_after),
        }
    elif scenario.metric == "floor_drop_down":
        finding = {
            "type": scenario.metric,
            "classic_attempts": attempts_to_drop_below_floor_after(classic, scenario.shift_after),
            "recency_attempts": attempts_to_drop_below_floor_after(recency, scenario.shift_after),
        }
    elif scenario.metric == "max_abs_diff":
        finding = {"type": scenario.metric, "value": max_abs_diff(classic, recency)}
    elif scenario.metric == "volatility":
        finding = {
            "type": scenario.metric,
            "classic": volatility_stats(classic),
            "recency": volatility_stats(recency),
        }
    else:  # pragma: no cover - guarded by the fixed SCENARIOS list above
        raise ValueError(f"unknown metric={scenario.metric!r}")

    return {
        "key": scenario.key,
        "name": scenario.name,
        "description": scenario.description,
        "responses": scenario.responses,
        "shift_after": scenario.shift_after,
        "floor": FLOOR,
        "trajectories": [
            {"key": "heuristic", "name": "Heuristic (streak-based)", "values": heuristic},
            {"key": "classic", "name": "Classic BKT", "values": classic},
            {"key": "recency", "name": "Recency-weighted BKT (Nirelle)", "values": recency},
        ],
        "finding": finding,
    }


def mastery_at_attempt(responses: list[bool], config: BKTConfig, attempt_number: int) -> float:
    p_mastery = PARAMS.p_init
    history: list[AttemptEvent] = []
    for idx, correct in enumerate(responses, start=1):
        attempt = AttemptEvent(correct=correct, response_time_ms=4000)
        p_mastery = update_mastery(p_mastery, history, attempt, PARAMS, config)
        history.append(attempt)
        if idx == attempt_number:
            return p_mastery
    return p_mastery


def recency_weight_sweep(responses: list[bool], attempt_number: int, weights: list[float]) -> list[dict]:
    """Mastery estimate at a fixed checkpoint attempt, as recency_weight
    varies from 0 (= classic BKT) upward, holding window/decay at
    BKTConfig's defaults. This is the "dial", not one fixed point on it.
    """
    return [
        {"recency_weight": round(w, 4), "value": mastery_at_attempt(responses, BKTConfig(recency_weight=w), attempt_number)}
        for w in weights
    ]


def find_crossing(points: list[dict], floor: float) -> float | None:
    """Linearly interpolate the recency_weight at which the swept value
    first reaches the floor, for an exact "crosses here" annotation.
    """
    for i in range(1, len(points)):
        prev, cur = points[i - 1], points[i]
        if prev["value"] < floor <= cur["value"]:
            span = cur["value"] - prev["value"]
            if span == 0:
                return cur["recency_weight"]
            frac = (floor - prev["value"]) / span
            return round(prev["recency_weight"] + frac * (cur["recency_weight"] - prev["recency_weight"]), 4)
    return None


def main() -> None:
    scenarios = [analyze_scenario(s) for s in SCENARIOS]

    primary = next(s for s in scenarios if s["key"] == "remediation_click")
    checkpoint_attempt = primary["shift_after"] + CHECKPOINT_OFFSET
    sweep_weights = [round(i * 0.025, 4) for i in range(29)]  # 0.000 .. 0.700
    sweep_points = recency_weight_sweep(SCENARIOS[0].responses, checkpoint_attempt, sweep_weights)
    crossing = find_crossing(sweep_points, FLOOR)

    representative_weights = sorted({0.0, 0.15, DEFAULT_RECENCY_WEIGHT, 0.5, 0.65})
    attempts_to_floor_by_weight = {
        w: attempts_to_cross_floor_after(
            bkt_trajectory(SCENARIOS[0].responses, BKTConfig(recency_weight=w)), SCENARIOS[0].shift_after
        )
        for w in representative_weights
    }

    sweep = {
        "checkpoint_attempt": checkpoint_attempt,
        "default_recency_weight": DEFAULT_RECENCY_WEIGHT,
        "crossing_recency_weight": crossing,
        "points": sweep_points,
        "attempts_to_floor_by_weight": attempts_to_floor_by_weight,
    }

    console_summary = {
        "floor": FLOOR,
        "params": {
            "p_init": PARAMS.p_init,
            "p_learn": PARAMS.p_learn,
            "p_slip": PARAMS.p_slip,
            "p_guess": PARAMS.p_guess,
        },
        "scenarios": {s["key"]: s["finding"] for s in scenarios},
        "sweep": {
            "checkpoint_attempt": checkpoint_attempt,
            "default_recency_weight": DEFAULT_RECENCY_WEIGHT,
            "crossing_recency_weight": crossing,
            "attempts_to_floor_by_weight": attempts_to_floor_by_weight,
        },
    }

    data = {
        "floor": FLOOR,
        "params": console_summary["params"],
        "scenarios": scenarios,
        "sweep": sweep,
    }

    out_path = Path(__file__).resolve().parent / "model_comparison_data.json"
    out_path.write_text(json.dumps(data, indent=2))
    print(json.dumps(console_summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
