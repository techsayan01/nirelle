"""Shared data types for anti-cheating / integrity signal detection."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SignalName(str, Enum):
    """The four independent integrity signals from the BRD."""

    RESPONSE_TIME_OUTLIER = "response_time_outlier"
    ANSWER_PATTERN_MISMATCH = "answer_pattern_mismatch"
    FOCUS_LOSS = "focus_loss"
    MASTERY_PREDICTION_MISMATCH = "mastery_prediction_mismatch"


@dataclass(frozen=True)
class QuestionAttempt:
    """One answered question within a session, as fed into signal detectors."""

    correct: bool
    response_time_ms: int
    difficulty: float  # normalized 0.0 (easiest) to 1.0 (hardest)

    def __post_init__(self) -> None:
        if not 0.0 <= self.difficulty <= 1.0:
            raise ValueError(f"difficulty={self.difficulty!r} must be in [0, 1]")


@dataclass(frozen=True)
class IntegritySignal:
    """The verdict of one detector, plus a human-readable reason."""

    name: SignalName
    triggered: bool
    detail: str


@dataclass(frozen=True)
class IntegrityAssessment:
    """Combined verdict across all signals for one session.

    Per the BRD, "no single signal is decisive on its own" - ``flagged`` is
    only True once at least ``min_triggered`` signals fire together.
    """

    signals: tuple[IntegritySignal, ...]
    min_triggered: int

    @property
    def triggered_signals(self) -> tuple[IntegritySignal, ...]:
        return tuple(s for s in self.signals if s.triggered)

    @property
    def flagged(self) -> bool:
        return len(self.triggered_signals) >= self.min_triggered
