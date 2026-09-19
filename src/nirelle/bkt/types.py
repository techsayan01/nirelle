"""Shared data types for the Nirelle mastery engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class LoopStage(str, Enum):
    """Stages of the remediation loop, per the BRD's flowchart."""

    DIAGNOSTIC = "diagnostic"
    REMEDIATION = "remediation"
    RETEST = "retest"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    TEACHER_RETEST = "teacher_retest"


@dataclass(frozen=True)
class AttemptEvent:
    """One answered question, as fed into the BKT update."""

    correct: bool
    response_time_ms: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stage: LoopStage = LoopStage.DIAGNOSTIC
    misconception_tag: str | None = None


@dataclass
class MasteryState:
    """Mutable per-(student, sub-skill) state owned by MasteryEngine."""

    student_id: str
    sub_skill_id: str
    p_mastery: float
    stage: LoopStage = LoopStage.DIAGNOSTIC
    cycle_count: int = 0
    history: list[AttemptEvent] = field(default_factory=list)

    @property
    def attempt_count(self) -> int:
        return len(self.history)
