"""Nirelle's core mastery-tracking engine.

Recency-weighted BKT plus the diagnose -> remediate -> re-test -> escalate
loop, and the anti-cheating integrity signals, from the Nirelle BRD. See
Nirelle-BRD.md for the product context this package implements.
"""
from .bkt import (
    DEFAULT_ENGINE_CONFIG,
    AttemptEvent,
    BKTConfig,
    EngineConfig,
    LoopStage,
    MasteryEngine,
    MasteryState,
    SkillParams,
    recency_weighted_rate,
    update_mastery,
)
from .bkt import DEFAULT_CONFIG as DEFAULT_BKT_CONFIG
from .integrity import (
    IntegrityAssessment,
    IntegrityConfig,
    IntegritySignal,
    QuestionAttempt,
    SignalName,
    assess_session,
    detect_answer_pattern_mismatch,
    detect_focus_loss,
    detect_mastery_prediction_mismatch,
    detect_response_time_outlier,
)
from .integrity import DEFAULT_CONFIG as DEFAULT_INTEGRITY_CONFIG
from .service import NotFoundError, RemediationService

__all__ = [
    "AttemptEvent",
    "BKTConfig",
    "DEFAULT_BKT_CONFIG",
    "DEFAULT_ENGINE_CONFIG",
    "DEFAULT_INTEGRITY_CONFIG",
    "EngineConfig",
    "IntegrityAssessment",
    "IntegrityConfig",
    "IntegritySignal",
    "LoopStage",
    "MasteryEngine",
    "MasteryState",
    "NotFoundError",
    "QuestionAttempt",
    "RemediationService",
    "SignalName",
    "SkillParams",
    "assess_session",
    "detect_answer_pattern_mismatch",
    "detect_focus_loss",
    "detect_mastery_prediction_mismatch",
    "detect_response_time_outlier",
    "recency_weighted_rate",
    "update_mastery",
]
