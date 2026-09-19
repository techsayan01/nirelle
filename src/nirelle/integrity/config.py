"""Tunable thresholds for integrity signal detection.

Defaults are reasonable starting points, not fit to data - tune them once
real pilot-school session logs are available, same caveat as BKTConfig.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrityConfig:
    # Signal 1: response-time outliers.
    hard_difficulty_threshold: float = 0.7
    suspiciously_fast_ms: int = 3000
    # Fraction of consecutive response-time deltas that flip direction
    # (fast/slow/fast...) before a session counts as "erratic".
    erratic_reversal_ratio: float = 0.5

    # Signal 2: answer-pattern-vs-difficulty mismatch.
    easy_difficulty_threshold: float = 0.3
    min_questions_per_bucket: int = 2
    pattern_mismatch_gap: float = 0.4  # hard_correct_rate - easy_correct_rate

    # Signal 4: mastery-prediction mismatch.
    low_mastery_threshold: float = 0.5
    high_retest_correct_rate: float = 0.9
    atypical_fast_ms: int = 2500

    # Composite: how many of the four signals must fire before the session
    # is flagged, since no single signal is decisive on its own.
    min_triggered_for_flag: int = 2

    def __post_init__(self) -> None:
        for name in (
            "hard_difficulty_threshold",
            "easy_difficulty_threshold",
            "erratic_reversal_ratio",
            "pattern_mismatch_gap",
            "low_mastery_threshold",
            "high_retest_correct_rate",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name}={value!r} must be in [0, 1]")

        if self.easy_difficulty_threshold >= self.hard_difficulty_threshold:
            raise ValueError(
                "easy_difficulty_threshold must be < hard_difficulty_threshold "
                f"(got {self.easy_difficulty_threshold!r} >= {self.hard_difficulty_threshold!r})"
            )
        if self.suspiciously_fast_ms < 0:
            raise ValueError(f"suspiciously_fast_ms={self.suspiciously_fast_ms!r} must be >= 0")
        if self.atypical_fast_ms < 0:
            raise ValueError(f"atypical_fast_ms={self.atypical_fast_ms!r} must be >= 0")
        if self.min_questions_per_bucket < 1:
            raise ValueError(
                f"min_questions_per_bucket={self.min_questions_per_bucket!r} must be >= 1"
            )
        if self.min_triggered_for_flag < 1:
            raise ValueError(
                f"min_triggered_for_flag={self.min_triggered_for_flag!r} must be >= 1"
            )
