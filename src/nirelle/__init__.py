"""Nirelle's core mastery-tracking engine.

Recency-weighted BKT plus the diagnose -> remediate -> re-test -> escalate
loop from the Nirelle BRD. See Nirelle-BRD.md for the product context this
package implements.
"""
from .bkt import (
    DEFAULT_CONFIG,
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

__all__ = [
    "AttemptEvent",
    "BKTConfig",
    "DEFAULT_CONFIG",
    "DEFAULT_ENGINE_CONFIG",
    "EngineConfig",
    "LoopStage",
    "MasteryEngine",
    "MasteryState",
    "SkillParams",
    "recency_weighted_rate",
    "update_mastery",
]
